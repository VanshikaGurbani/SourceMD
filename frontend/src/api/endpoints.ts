import { apiClient } from "./client";
import type { ClaimOut, EvaluationOut } from "./types";

export async function evaluate(
  question: string,
  aiAnswer: string
): Promise<EvaluationOut> {
  const { data } = await apiClient.post<EvaluationOut>("/evaluate", {
    question,
    ai_answer: aiAnswer,
  });
  return data;
}

export async function getEvaluation(id: number): Promise<EvaluationOut> {
  const { data } = await apiClient.get<EvaluationOut>(`/history/${id}`);
  return data;
}

export async function sendFollowUp(
  question: string,
  originalQuestion: string,
  aiAnswer: string,
  correctedAnswer: string,
  claims: ClaimOut[]
): Promise<{ answer: string }> {
  const { data } = await apiClient.post("/follow-up", {
    question,
    original_question: originalQuestion,
    ai_answer: aiAnswer,
    corrected_answer: correctedAnswer,
    claims: claims.map((c) => ({ verdict: c.verdict, text: c.text })),
  });
  return data;
}
