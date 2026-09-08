import {BrandLogo} from "./BrandLogo";

export function AuthTransition({message}:{message:string}){
  return <div className="auth-transition" role="status" aria-live="polite" aria-label={message}>
    <div className="auth-transition-card">
      <BrandLogo variant="black" className="auth-transition-brand"/>
      <span className="auth-transition-spinner" aria-hidden="true"/>
      <b>{message}</b>
      <small>Mohon tunggu sebentar</small>
    </div>
  </div>;
}
