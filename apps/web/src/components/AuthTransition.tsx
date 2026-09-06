export function AuthTransition({message}:{message:string}){
  return <div className="auth-transition" role="status" aria-live="polite" aria-label={message}>
    <div className="auth-transition-card">
      <span className="auth-transition-brand">teamku</span>
      <span className="auth-transition-spinner" aria-hidden="true"/>
      <b>{message}</b>
      <small>Mohon tunggu sebentar</small>
    </div>
  </div>;
}
