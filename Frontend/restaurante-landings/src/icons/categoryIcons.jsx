import { CiFries } from "react-icons/ci";
import { GiChickenLeg } from "react-icons/gi";
import { LuCupSoda } from "react-icons/lu";

const REACT_CATEGORY_ICONS = Object.freeze({
  CiFries,
  GiChickenLeg,
  LuCupSoda,
});

const DEFAULT_CATEGORY_ICON = "fa-solid fa-utensils";
const FONT_AWESOME_PREFIX = /^(?:fa-|fas(?:\s|$)|far(?:\s|$)|fab(?:\s|$))/i;

export function CategoryIcon({ icon }) {
  const iconName = typeof icon === "string" ? icon.trim() : "";
  const resolvedIcon = iconName || DEFAULT_CATEGORY_ICON;

  if (FONT_AWESOME_PREFIX.test(resolvedIcon)) {
    return <i className={resolvedIcon} aria-hidden="true"></i>;
  }

  const ReactIcon = REACT_CATEGORY_ICONS[resolvedIcon];

  if (ReactIcon) {
    return <ReactIcon aria-hidden="true" focusable="false" />;
  }

  return <i className={resolvedIcon} aria-hidden="true"></i>;
}
