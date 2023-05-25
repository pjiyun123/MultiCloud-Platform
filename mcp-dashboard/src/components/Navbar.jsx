import React, { useEffect } from "react";
import { RiNotification3Line } from "react-icons/ri";
import { MdKeyboardArrowDown } from "react-icons/md";

import profilePic from "../data/profilePic.png";
import { UserProfile, Notification } from ".";
import { useStateContext } from "../contexts/ContextProvider";

const NavButton = ({ customFunc, icon, color, dotColor }) => (
  <button
    type="button"
    onClick={() => customFunc()}
    style={{ color }}
    className="relative text-xl rounded-full p-3 hover:bg-light-gray"
  >
    <span
      style={{ background: dotColor }}
      className="absolute inline-flex rounded-full h-2 w-2 right-2 top-2"
    />
    {icon}
  </button>
);

const Navbar = () => {
  const {
    mainColor,
    handleClick,
    isClicked,
    isAuthorized,
    setIsAuthorized
  } = useStateContext();

  return (
    <div className="flex justify-end p-2 md:ml-6 md:mr-6 relative">
      <div className="flex">
        <button onClick={() => {
            setIsAuthorized(!isAuthorized);
            localStorage.clear();
        }}>
          logout
        </button>
        <NavButton
          dotColor="#EA4336"
          customFunc={() => handleClick("notification")}
          color={mainColor}
          icon={<RiNotification3Line />}
        />
        <div
          className="flex items-center gap-2 cursor-pointer p-1 hover:bg-light-gray rounded-lg ml-4"
          onClick={() => handleClick("userProfile")}
        >
          <img
            className="rounded-full w-8 h-8"
            src={profilePic}
            alt="user-profile"
          />
          <p>
            <span className="text-gray-400 text-14">안녕하세요,</span>{" "}
            <span className="text-gray-400 font-bold ml-1 text-15">
              승기
            </span>
            <span className="text-gray-400 text-14">님</span>{" "}
          </p>
          <MdKeyboardArrowDown className="text-gray-400 text-14" />
        </div>

        {isClicked.notification && <Notification />}
        {isClicked.userProfile && <UserProfile />}
      </div>
    </div>
  );
};

export default Navbar;
