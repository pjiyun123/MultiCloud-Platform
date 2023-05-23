import datetime

from sqlalchemy.orm import Session

from db.model import task_model as models


def create_task(
    db: Session,
    task_id: str,
    task_name: str,
    user_id: int,
    deploy_id: int,
    username: str,
    team: str,
    action: str,
):
    db_task = models.Task(
        task_id=task_id,
        task_name=task_name,
        user_id=user_id,
        deploy_id=deploy_id,
        username=username,
        team=team,
        created_at=datetime.datetime.now(),
        action=action,
    )
    try:
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task
    except Exception as err:
        raise err


def get_all_tasks(db: Session, skip: int = 0, limit: int = 100):
    try:
        db_query = db.query(models.Tasks)

        return (
            db_query.order_by(models.Tasks.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as err:
        raise err


def get_all_tasks_by_team(db: Session, team: str, skip: int = 0, limit: int = 100):
    try:
        result = []
        for i in team:
            result.extend(
                db.query(models.Tasks)
                .filter(models.Tasks.team == i)
                .order_by(models.Tasks.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
        return result
    except Exception as err:
        raise err


def get_tasks_by_deploy_id(db: Session, deploy_id: int):
    try:
        return db.query(models.Tasks).filter(models.Tasks.deploy_id == deploy_id).all()
    except Exception as err:
        raise err
