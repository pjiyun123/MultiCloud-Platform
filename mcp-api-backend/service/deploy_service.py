from fastapi import Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from entity import deploy_entity as schemas_deploy
from repository import deploy_repository as crud_deploys
from repository import deploy_detail_repository as crud_deploy_details
from repository import stack_repository as crud_stacks
from db.connection import get_db
from repository import activity_logs_repository as crud_activity
from src.shared.security import deps

from repository import task_repository as crud_tasks
from repository import aws_repository as crud_aws
from repository import gcp_repository as crud_gcp
from repository import azure_repository as crud_azure
from repository import custom_provider_repository as crud_custom_provider
from entity import user_entity as schemas_users
from repository import user_repository as crud_users
from service import airflow_service
from utils.utils import check_team_user


async def deploy_infra_from_list(
    response: Response,
    deploy: schemas_deploy.DeployCreate,
    current_user: schemas_users.User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
):

    response.status_code = status.HTTP_202_ACCEPTED
    team = deploy.team
    # 현재 사용자의 팀과 요청한 팀을 비교하여 권한이 있는지 확인
    if not crud_users.is_master(db, current_user):
        current_team = current_user.team
        if not check_team_user(current_team, [deploy.team]):
            raise HTTPException(
                status_code=403, detail=f"팀 {team} 에 충분한 권한이 없습니다."
            )
    

    # 팀과 이름으로 타겟 스택을 구하고, 해당 스택의 CSP 타입을 보고 적절한 Provider를 구함
    infra_data = {}
    target_stacks = []
    for deploy_detail in deploy.deploy_detail:
        stack_name = deploy_detail.stack_name
        variables = deploy_detail.variables
        stack = crud_stacks.get_stack_by_name_and_team(db, stack_name, team)
        if (stack):
            provider = None
            if (stack.csp_type == "aws"):
                res = crud_aws.get_credentials_aws_profile(db, deploy.environment, team)
                provider = {
                    "access_key_id": res.get("access_key"),
                    "secret_access_key": res.get("secret_access_key"),
                }
            elif (stack.csp_type == "gcp"):
                res = crud_gcp.get_team_gcloud_profile(db, team, deploy.environment)
                provider = {
                    "credentials": res.credentials,
                }
            elif (stack.csp_type == "azure"):
                res = crud_azure.get_team_azure_profile(db, team, deploy.environment)
                provider = {
                    "client_id": res.client_id,
                    "client_secret": res.client_secret,
                    "tenant_id": res.tenant_id,
                    "subscription_id": res.subscription_id,
                }
            elif (stack.csp_type == "custom"):
                res = crud_custom_provider.get_team_custom_provider_profile(db, team, deploy.environment)
                provider = {
                    "credentials": res.credentials,
                }
            
            if not (provider):
                raise HTTPException(
                    status_code=404, detail=f"Provider 정보를 찾을 수 없습니다."
                )

            infra_data[stack_name] = {
                "csp_type": stack.csp_type,
                "stack_type": stack.stack_type,
                "variables": variables,
                "tfvar_file": deploy_detail.tfvar_file,
                "provider": provider
            }
            target_stacks.append(stack)
        else:
            raise HTTPException(
                status_code=404, detail=f"스택 {stack_name} 을 찾을 수 없습니다."
            )
    
    # 배포할 인프라의 정보를 Airflow로 전달하며 배포 요청
    airflow_conf = {
        "deploy_name": deploy.deploy_name,
        "team": deploy.team,
        "environment": deploy.environment,
        "start_time": deploy.start_time,
        "destroy_time": deploy.destroy_time,
        "infra_data": infra_data,
    }
    trigger_result = airflow_service.trigger_dag(
        dag_id="mcp_deploy_dag",
        conf=airflow_conf
    )

    dag_run_id = trigger_result.get("dag_run_id", None)
    assert airflow_conf == trigger_result.get("conf", {})
    assert dag_run_id is not None


    # deploy 테이블 업데이트
    db_deploy = crud_deploys.create_new_deploy(
        db=db,
        deploy=deploy,
        user_id=current_user.id,
        team=team,
        task_id=dag_run_id,
        username=current_user.username,
    )

    # deploy_detail 테이블 업데이트
    for detail, stack in zip(deploy.deploy_detail, target_stacks):
        db_deploy_detail = crud_deploy_details.create_new_deploy_detail(
            db=db,
            deploy_id=db_deploy.deploy_id,
            stack_id=stack.stack_id,
            deploy_detail=detail
        )

    # task 테이블 업데이트
    name_of_stacks = '+'.join(stack.stack_name for stack in target_stacks)
    db_task = crud_tasks.create_task(
        db=db,
        task_id=dag_run_id,
        task_name=f"{name_of_stacks}-{team}-{deploy.environment}-{deploy.deploy_name}",
        user_id=current_user.id,
        deploy_id=db_deploy.deploy_id,
        username=current_user.username,
        team=team,
        action="List Apply"
    )

    # activity 로깅
    crud_activity.create_activity_log(
        db=db,
        username=current_user.username,
        team=current_user.team,
        action=f"인프라 배포 요청 ({deploy.deploy_name})",
    )
    
    return {
        "name": name_of_stacks,  # TODO: 반환값 확실하게
        "run_id": dag_run_id
    }


    
    # Get  credentials by providers supported
    secreto = check_prefix(
        db, stack_name=deploy.stack_name, environment=deploy.environment, team=team
    )
    # Get info from stack data
    stack_data = stack(db, stack_name=deploy.stack_name)
    branch = (
        stack_data.branch
        if deploy.stack_branch == "" or deploy.stack_branch == None
        else deploy.stack_branch
    )
    git_repo = stack_data.git_repo
    tf_ver = stack_data.tf_version
    check_deploy_exist(db, deploy.name, team,
                       deploy.environment, deploy.stack_name)
    check_deploy_task_pending_state(deploy.name, team, deploy.environment)
    try:
        # check crontime
        check_cron_schedule(deploy.start_time)
        check_cron_schedule(deploy.destroy_time)
        # push task Deploy to queue and return task_id
        pipeline_deploy = async_deploy(
            git_repo,
            deploy.name,
            deploy.stack_name,
            deploy.environment,
            team,
            branch,
            tf_ver,
            deploy.variables,
            secreto,
            deploy.tfvar_file,
            deploy.project_path,
            current_user.username,
        )
        # Push deploy task data
        db_deploy = crud_deploys.create_new_deploy(
            db=db,
            deploy=deploy,
            stack_branch=branch,
            task_id=pipeline_deploy,
            action="Apply",
            team=team,
            user_id=current_user.id,
            username=current_user.username,
        )
        # Push task data
        db_task = crud_tasks.create_task(
            db=db,
            task_id=pipeline_deploy,
            task_name=f"{deploy.stack_name}-{team}-{deploy.environment}-{deploy.name}",
            user_id=current_user.id,
            deploy_id=db_deploy.id,
            username=current_user.username,
            team=team,
            action="Apply",
        )

        return {"task": db_task}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"{err}")
    finally:
        try:
            # async_schedule_delete(db_deploy.id, team)
            # # Add schedule
            # async_schedule_add(db_deploy.id, team)
            ...
        except Exception as err:
            print(err)


async def get_deploy_status(
    run_id: str,
    current_user: schemas_users.User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
):
    print(run_id)
    status_result = airflow_service.get_task_status(
        dag_id="mcp_deploy_dag",
        dag_run_id=run_id
    )
    task_instances = status_result.get("task_instances", [])

    result = []
    for task_instance in task_instances:
        result.append(
            schemas_deploy.DeployStatus(
                task_id=task_instance.get("task_id", ""),
                status=task_instance.get("state", "")
            )
        )

    return result

async def get_deploy_logs(
    run_id: str,
    task_id: str,
    current_user: schemas_users.User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
):
    print(run_id, task_id)
    log_result = airflow_service.get_task_log(
        dag_id="mcp_deploy_dag",
        dag_run_id=run_id,
        task_id=task_id
    )

    crud_activity.create_activity_log(
        db=db,
        username=current_user.username,
        team=current_user.team,
        action=f"배포 Task 로그 조회 ({run_id}:{task_id})",
    )
    return log_result