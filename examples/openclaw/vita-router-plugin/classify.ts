// ------------------------------------------------------------------
// Classificação de intenção CRUD — sem LLM, regex puro
//
// Retorna "complex" quando não tem certeza. Nunca tenta ser
// esperto demais: "terminei de pensar sobre cancelar o dentista"
// NÃO vira "complete" nem "cancel". Múltiplos verbos = complex.
// ------------------------------------------------------------------

export interface VitaIntent {
  type: "complete" | "add" | "cancel" | "start" | "complex";
  params: Record<string, string>;
  confidence: number;
}

const PATTERNS: Array<{
  regex: RegExp;
  type: VitaIntent["type"];
  extract: (m: RegExpMatchArray) => Record<string, string>;
}> = [
  {
    regex: /^(?:terminei|concluí|fiz|completei|feito|pronto)[:\s]+(.+)$/i,
    type: "complete",
    extract: (m) => ({ description: m[1].trim() }),
  },
  {
    regex: /^(?:adiciona|cria|nova)\s+task[:\s]+(.+)$/i,
    type: "add",
    extract: (m) => ({ description: m[1].trim() }),
  },
  {
    regex: /^(?:cancela|desiste|remove)[:\s]+(.+)$/i,
    type: "cancel",
    extract: (m) => ({ description: m[1].trim() }),
  },
  {
    regex: /^(?:comecei|iniciei|começando|starting)[:\s]+(.+)$/i,
    type: "start",
    extract: (m) => ({ description: m[1].trim() }),
  },
];

// Verbos de ação de todos os padrões — se a descrição capturada
// contém algum deles, a frase é ambígua e deve ser "complex".
// Ex: "terminei de pensar sobre cancelar o dentista" → complex
// Inclui formas conjugadas E infinitivos pra pegar "cancelar",
// "terminar", "completar" etc. dentro da descrição capturada.
const ACTION_VERBS =
  /\b(?:termin(?:ei|ar|ou)|conclu(?:í|ir|iu)|f(?:iz|azer|ez)|complet(?:ei|ar|ou)|feit[oa]|pront[oa]|adicion(?:a|ar|ou)|cri(?:a|ar|ou)|nov[oa]|cancel(?:a|ar|ou)|desist(?:e|ir|iu)|remov(?:e|er|eu)|comec(?:ei|ar|ou)|inici(?:ei|ar|ou)|começando|starting)\b/i;

/**
 * Classifica a intenção do usuário sem LLM.
 *
 * Usa keyword matching com padrões de alta confiança.
 * Se a frase não bate com nenhum padrão claro, retorna
 * type: "complex" para delegar à Vita via sessão.
 *
 * Guard: se a descrição capturada contém outro verbo de ação,
 * a frase é ambígua (múltiplos verbos) → retorna "complex".
 */
export function classifyIntent(message: string): VitaIntent {
  const lower = message.toLowerCase().trim();

  for (const { regex, type, extract } of PATTERNS) {
    const match = lower.match(regex);
    if (match) {
      const params = extract(match);

      // Múltiplos verbos de ação = ambíguo → complex
      if (params.description && ACTION_VERBS.test(params.description)) {
        return { type: "complex", params: {}, confidence: 0 };
      }

      return { type, params, confidence: 0.9 };
    }
  }

  return { type: "complex", params: {}, confidence: 0 };
}
