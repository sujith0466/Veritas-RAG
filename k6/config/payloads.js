/**
 * Veritas RAG V2 k6 Payloads & Fixtures
 */

export const SAMPLE_PROMPTS = [
  'What are the compliance requirements for GDPR document retention?',
  'Explain the multi-tenant architecture and isolation guarantees of Veritas RAG.',
  'How does the quota governor enforce monthly token limits?',
  'Summarize the primary security features of enterprise RAG systems.',
  'What are the disaster recovery steps for restoring a PostgreSQL database?',
];

export function getRandomPrompt() {
  const index = Math.floor(Math.random() * SAMPLE_PROMPTS.length);
  return SAMPLE_PROMPTS[index];
}

export function generateDummyDocument(sizeKb = 50) {
  const content = 'Veritas RAG enterprise compliance document test content. '.repeat(sizeKb * 15);
  return {
    filename: `load_test_doc_${Date.now()}_${Math.random().toString(36).substring(7)}.txt`,
    content: content,
    mimeType: 'text/plain',
  };
}
