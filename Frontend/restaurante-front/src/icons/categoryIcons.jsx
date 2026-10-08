import { CiFries } from "react-icons/ci";
import { GiChickenLeg } from "react-icons/gi";
import { LuCupSoda } from "react-icons/lu";

const REACT_CATEGORY_ICONS = Object.freeze({
  CiFries,
  GiChickenLeg,
  LuCupSoda,
});

export function CategoryIcon({ icon }) {
  const iconName = typeof icon === "string" ? icon.trim() : "";
  const ReactIcon = REACT_CATEGORY_ICONS[iconName];

  if (ReactIcon) {
    return <ReactIcon aria-hidden="true" focusable="false" />;
  }

  return <i className={iconName} aria-hidden="true"></i>;
}
