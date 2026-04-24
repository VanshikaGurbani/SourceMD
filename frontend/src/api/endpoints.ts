import { apiClient } from "./client";
import type {
  EvaluationListItem,
  EvaluationOut,
  Token,
  UserOut,
} from "./types";

export async function register(email: string, password: string): Promise<UserOut> {
  const { data } = await apiClient.post<UserOut>("/auth/register", { email, password });
  return data;
}

export async function login(email: string, password: string): Promise<Token> {
  const { data } = await apiClient.post<Token>("/auth/login", { email, password });
  return data;
}

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

export async function listHistory(): Promise<EvaluationListItem[]> {
  const { data } = await apiClient.get<EvaluationListItem[]>("/history");
  return data;
}

export async function getEvaluation(id: number): Promise<EvaluationOut> {
  const { data } = await apiClient.get<EvaluationOut>(`/history/${id}`);
  return data;
}

export async function deleteEvaluation(id: number): Promise<void> {
  await apiClient.delete(`/history/${id}`);
}

export async function sendFollowUp(
  evaluationId: number,
  question: string
): Promise<{ answer: string; evaluation_id: number }> {
  const { data } = await apiClient.post("/follow-up", {
    evaluation_id: evaluationId,
    question,
  });
  return data;
}
