export type Verdict = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";

export interface SourceCitation {
  doc: string;
  page: number;
  chunk: number;
  score: number;
  text: string;
  source_url?: string;
  web_url?: string;
}

export interface ClaimOut {
  id: number;
  text: string;
  verdict: Verdict;
  confidence: number;
  rationale: string;
  sources: SourceCitation[];
}

export interface EvaluationOut {
  id: string;
  question: string;
  ai_answer: string;
  trust_score: number;
  ragas_faithfulness: number | null;
  ragas_context_precision: number | null;
  corrected_answer: string;
  follow_up_questions: string[];
  created_at: string;
  claims: ClaimOut[];
}

export interface EvaluationListItem {
  id: string;
  question: string;
  trust_score: number;
  created_at: string;
}
