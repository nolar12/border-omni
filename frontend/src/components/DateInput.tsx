import React, { useState, useEffect } from 'react';

interface DateInputProps {
  value: string; // YYYY-MM-DD
  onChange: (value: string) => void; // returns YYYY-MM-DD
  className?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  id?: string;
  name?: string;
}

function toDisplay(iso: string): string {
  if (!iso) return '';
  const parts = iso.split('-');
  if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
  return iso;
}

function toISO(display: string): string {
  const parts = display.split('/');
  if (parts.length === 3 && parts[2].length === 4) {
    return `${parts[2]}-${parts[1]}-${parts[0]}`;
  }
  return '';
}

const DateInput: React.FC<DateInputProps> = ({
  value,
  onChange,
  className,
  placeholder = 'DD/MM/AAAA',
  required,
  disabled,
  id,
  name,
}) => {
  const [display, setDisplay] = useState<string>(toDisplay(value));

  useEffect(() => {
    setDisplay(toDisplay(value));
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 8);
    let masked = raw;
    if (raw.length > 4) {
      masked = `${raw.slice(0, 2)}/${raw.slice(2, 4)}/${raw.slice(4)}`;
    } else if (raw.length > 2) {
      masked = `${raw.slice(0, 2)}/${raw.slice(2)}`;
    }
    setDisplay(masked);
    if (raw.length === 8) {
      const iso = toISO(masked);
      if (iso) onChange(iso);
    } else {
      onChange('');
    }
  };

  return (
    <input
      id={id}
      name={name}
      type="text"
      inputMode="numeric"
      value={display}
      onChange={handleChange}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      className={className}
      maxLength={10}
    />
  );
};

export default DateInput;
