"use client";
import {ComponentPropsWithoutRef, useId, useState} from "react";
import {Icon} from "./Icon";

type PasswordInputProps = Omit<ComponentPropsWithoutRef<"input">, "type">;

export function PasswordInput({id, disabled, ...props}: PasswordInputProps) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const [visible, setVisible] = useState(false);
  const revealed = visible && !disabled;
  const action = revealed ? "Sembunyikan kata sandi" : "Tampilkan kata sandi";

  return (
    <div className="password-input">
      <input {...props} id={inputId} disabled={disabled} type={revealed ? "text" : "password"} />
      <button
        className="password-toggle" type="button" disabled={disabled}
        aria-label={action} aria-controls={inputId} title={action}
        onClick={() => setVisible(current => !current)}
      >
        <Icon name={revealed ? "eye-off" : "eye"} size={20} />
      </button>
    </div>
  );
}
