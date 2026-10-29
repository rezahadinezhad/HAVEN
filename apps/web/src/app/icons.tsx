"use client";
import { ChatCircleDotsIcon } from "@phosphor-icons/react/dist/csr/ChatCircleDots";
import { UsersIcon } from "@phosphor-icons/react/dist/csr/Users";
import { DevicesIcon } from "@phosphor-icons/react/dist/csr/Devices";
import { KeyIcon } from "@phosphor-icons/react/dist/csr/Key";
import { GearSixIcon } from "@phosphor-icons/react/dist/csr/GearSix";
import { LifebuoyIcon } from "@phosphor-icons/react/dist/csr/Lifebuoy";
import { SquaresFourIcon } from "@phosphor-icons/react/dist/csr/SquaresFour";
import { LockSimpleIcon } from "@phosphor-icons/react/dist/csr/LockSimple";
import { SignOutIcon } from "@phosphor-icons/react/dist/csr/SignOut";
import { PlusIcon } from "@phosphor-icons/react/dist/csr/Plus";
import { MagnifyingGlassIcon } from "@phosphor-icons/react/dist/csr/MagnifyingGlass";
import { ArrowUpIcon } from "@phosphor-icons/react/dist/csr/ArrowUp";
import { ArrowRightIcon } from "@phosphor-icons/react/dist/csr/ArrowRight";
import { ArrowLeftIcon } from "@phosphor-icons/react/dist/csr/ArrowLeft";
import { MicrophoneIcon } from "@phosphor-icons/react/dist/csr/Microphone";
import { StopIcon } from "@phosphor-icons/react/dist/csr/Stop";
import { PaperclipIcon } from "@phosphor-icons/react/dist/csr/Paperclip";
import { ShieldWarningIcon } from "@phosphor-icons/react/dist/csr/ShieldWarning";
import { ShieldCheckIcon } from "@phosphor-icons/react/dist/csr/ShieldCheck";
import { MoonIcon } from "@phosphor-icons/react/dist/csr/Moon";
import { SunIcon } from "@phosphor-icons/react/dist/csr/Sun";
import { DotsThreeIcon } from "@phosphor-icons/react/dist/csr/DotsThree";
import { XIcon } from "@phosphor-icons/react/dist/csr/X";
import { GlobeHemisphereWestIcon } from "@phosphor-icons/react/dist/csr/GlobeHemisphereWest";
import { HeartIcon } from "@phosphor-icons/react/dist/csr/Heart";
import { ArrowBendUpLeftIcon } from "@phosphor-icons/react/dist/csr/ArrowBendUpLeft";
import { CaretDownIcon } from "@phosphor-icons/react/dist/csr/CaretDown";
import { CheckIcon } from "@phosphor-icons/react/dist/csr/Check";
import { ChecksIcon } from "@phosphor-icons/react/dist/csr/Checks";
import { ClockIcon } from "@phosphor-icons/react/dist/csr/Clock";
import { SmileyIcon } from "@phosphor-icons/react/dist/csr/Smiley";
import { CopyIcon } from "@phosphor-icons/react/dist/csr/Copy";
import { PencilSimpleIcon } from "@phosphor-icons/react/dist/csr/PencilSimple";
import { TrashIcon } from "@phosphor-icons/react/dist/csr/Trash";
import { ImageIcon } from "@phosphor-icons/react/dist/csr/Image";
import { PlayIcon } from "@phosphor-icons/react/dist/csr/Play";
import { MusicNoteIcon } from "@phosphor-icons/react/dist/csr/MusicNote";
import { FileIcon } from "@phosphor-icons/react/dist/csr/File";
const icons = {
  messages: ChatCircleDotsIcon,
  people: UsersIcon,
  devices: DevicesIcon,
  key: KeyIcon,
  settings: GearSixIcon,
  help: LifebuoyIcon,
  admin: SquaresFourIcon,
  lock: LockSimpleIcon,
  logout: SignOutIcon,
  plus: PlusIcon,
  search: MagnifyingGlassIcon,
  send: ArrowUpIcon,
  next: ArrowRightIcon,
  back: ArrowLeftIcon,
  microphone: MicrophoneIcon,
  stop: StopIcon,
  attachment: PaperclipIcon,
  warning: ShieldWarningIcon,
  shield: ShieldCheckIcon,
  moon: MoonIcon,
  sun: SunIcon,
  more: DotsThreeIcon,
  close: XIcon,
  language: GlobeHemisphereWestIcon,
  heart: HeartIcon,
  reply: ArrowBendUpLeftIcon,
  down: CaretDownIcon,
  check: CheckIcon,
  checks: ChecksIcon,
  clock: ClockIcon,
  emoji: SmileyIcon,
  copy: CopyIcon,
  edit: PencilSimpleIcon,
  delete: TrashIcon,
  image: ImageIcon,
  play: PlayIcon,
  music: MusicNoteIcon,
  file: FileIcon,
};
export type IconName = keyof typeof icons;
export function Icon({
  name,
  size = 20,
  className = "",
  filled = false,
}: {
  name: IconName;
  size?: number;
  className?: string;
  filled?: boolean;
}) {
  const Glyph = icons[name];
  return (
    <Glyph
      className={`icon ${className}`}
      size={size}
      weight={filled ? "fill" : "regular"}
      aria-hidden="true"
      focusable="false"
    />
  );
}
export function HavenEmblem({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={compact ? "haven-emblem compact" : "haven-emblem"}
      aria-hidden="true"
    >
      <div className="emblem-orbit" />
      <div className="emblem-sheet rear" />
      <div className="emblem-sheet middle" />
      <div className="emblem-sheet front">
        <Icon name="messages" size={58} filled />
      </div>
      <div className="emblem-lock">
        <Icon name="lock" size={23} filled />
      </div>
    </div>
  );
}
