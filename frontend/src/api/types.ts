export type Verdict = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";

export interface SourceCitation {
  doc: string;
  page: number;
  chunk: number;
  score: number;
  text: string;
  source_url?: string;  // PDF download URL
  web_url?: string;     // canonical guideline webpage
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
  id: number;
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
  id: number;
  question: string;
  trust_score: number;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserOut {
  id: number;
  email: string;
  created_at: string;
}
