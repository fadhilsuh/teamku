import teamkuBlack from "../assets/brand/teamku-black.png";
import teamkuWhite from "../assets/brand/teamku-white.png";

const assets = {
  black: teamkuBlack,
  white: teamkuWhite,
} as const;

export function BrandLogo({
  variant,
  className = "brand-logo",
}: {
  variant: "white" | "black";
  className?: string;
}) {
  const asset = assets[variant];
  return (
    <img
      className={className}
      src={asset.src}
      alt="Teamku"
      width={asset.width}
      height={asset.height}
    />
  );
}
