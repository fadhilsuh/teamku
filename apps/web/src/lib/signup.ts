export type SignupValues = {
  company_name: string;
  admin_name: string;
  email: string;
  password: string;
};
export type SignupErrors = Partial<Record<keyof SignupValues, string>>;

export function validateSignup(values: SignupValues): SignupErrors {
  const errors: SignupErrors = {};
  const rules = {
    company_name: {label: "Nama perusahaan", min: 2, max: 120},
    admin_name: {label: "Nama Anda", min: 2, max: 100},
    email: {label: "Email kerja", min: 5, max: 150},
    password: {label: "Kata sandi", min: 8, max: 128},
  };
  for (const field of Object.keys(rules) as (keyof SignupValues)[]) {
    const {label, min, max} = rules[field];
    const value = field === "password" ? values[field] : values[field].trim();
    const length = [...value].length;
    if (!length) errors[field] = `${label} wajib diisi.`;
    else if (length < min) errors[field] = `${label} minimal ${min} karakter.`;
    else if (length > max) errors[field] = `${label} maksimal ${max} karakter.`;
    else if (field === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      errors[field] = "Masukkan alamat email yang valid, misalnya nama@perusahaan.com.";
    }
  }
  return errors;
}
