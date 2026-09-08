import Link from "next/link";
import {ReactNode} from "react";
import {BrandLogo} from "./BrandLogo";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <main className="login-page">
      <section className="login-art">
        <div className="login-logo"><BrandLogo variant="white"/></div>
        <div>
          <p className="eyebrow" style={{color: "#fff"}}>powered by movon digital house</p>
          <h1>Presence with purpose.</h1>
          <p>Kelola kehadiran, agenda harian, dan keputusan tim dalam satu ruang kerja yang tenang dan jelas.</p>
        </div>
      </section>
      <section className="login-form-wrap">
        <div className="login-form">
          <h2>{title}</h2>
          <p className="muted">{subtitle}</p>
          {children}
        </div>
      </section>
    </main>
  );
}

export function AuthLinks({children}: {children: ReactNode}) {
  return <p className="auth-links">{children}</p>;
}

export function AuthLink({href, children}: {href: string; children: ReactNode}) {
  return <Link href={href}>{children}</Link>;
}
