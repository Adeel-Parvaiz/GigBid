// Approval payloads are free-form dicts in the OpenAPI schema (LangGraph interrupt values), so they are typed by hand here.
export interface Evidence { evidence_id: string; title: string; summary: string; skills: string[]; outcome?: string | null; source?: string; type?: string; date?: string | null }
export interface ClaimT { text: string; evidence_ids: string[]; kind: string; section: string }
export interface Verdict { text: string; label: string; support: number; reason?: string }
export interface Compliance { passed: boolean; violations: { rule: string; match: string; action: string }[]; blocking_reasons: string[] }
export interface ProposalPayload {
  kind: "proposal_approval"; job: { id: string; title: string };
  edit_diff?: string;
  draft: { claims: ClaimT[]; cover_letter: string; screening_answers: string[]; questions: string[] };
  claim_verification: Verdict[]; evidence: Evidence[];
  risk_report: { score: number; flags: string[]; explanation: string };
  price_quote: { amount: number; currency: string; rationale: string; connects_cost: number; affordable: boolean };
  critique?: { passed: boolean; score: number; issues: string[] } | null;
  compliance_verdict: Compliance; dry_run: { would_send?: Record<string, unknown>; connects_cost: number };
  blocking_reasons: string[]; allowed_actions: string[]; error?: string;
}
export interface MessagePayload {
  kind: "message_approval"; thread_id: string; intent: { intent: string; flags: string[] }; client_message: string;
  edit_diff?: string;
  draft: { claims: ClaimT[]; text: string; offered_slots: string[] }; evidence: Evidence[];
  compliance_verdict: Compliance; blocking_reasons: string[]; allowed_actions: string[]; error?: string;
}
export type Payload = ProposalPayload | MessagePayload;
export interface RunEvent { seq: number; type: "started" | "node" | "interrupt" | "done" | "error"; node?: string; wrote?: string[]; status?: string; message?: string; trace_id?: string; payload?: Payload }
