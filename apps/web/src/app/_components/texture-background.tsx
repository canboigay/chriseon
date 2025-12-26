import React from "react";

function buildTextureText(): string {
  const lines: string[] = [];

  // Simple enumerations + system-ish tokens; keep it readable but low-contrast.
  for (let row = 1; row <= 80; row += 1) {
    const n = String(row).padStart(2, "0");
    const seq = Array.from({ length: 18 }, (_, i) => String(row * 18 + i).padStart(3, "0")).join(
      " "
    );
    const tokens = [
      `pass_${n}: draft`,
      `pass_${n}: refine`,
      `model_a`,
      `model_b`,
      `model_c`,
      `score`,
      `consensus`,
    ].join(" · ");

    lines.push(`${seq}    ${tokens}`);
  }

  return lines.join("\n");
}

export function TextureBackground() {
  const text = buildTextureText();

  return (
    <div
      aria-hidden="true"
      className="chr-texture fixed inset-0 -z-10 overflow-hidden whitespace-pre px-6 py-10"
    >
      {text}
    </div>
  );
}
