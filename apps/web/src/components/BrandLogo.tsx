export function BrandLogo({
  variant,
  className = "brand-logo",
}: {
  variant: "white" | "black";
  className?: string;
}) {
  return (
    <img
      className={className}
      src={variant === "white" ? "/brand/teamku-white.png" : "/brand/teamku-black.png"}
      alt="Teamku"
    />
  );
}
