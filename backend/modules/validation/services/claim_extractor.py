import re

class ClaimExtractor:
    def __init__(self):
        self._sentence_split = re.compile(r'([A-Z][^.!?]*[.!?])', re.DOTALL)
        self._citation_marker = re.compile(r'\[(\d+)\]')

    def extract_atomic_claims(self, answer_text: str) -> list[tuple[str, int | None]]:
        """
        Splits answer text into sentences and extracts the associated citation marker.
        Returns a list of (sentence, citation_index) tuples.
        """
        sentences = self._sentence_split.findall(answer_text)
        if not sentences:
            sentences = [answer_text]
            
        results = []
        for sentence in sentences:
            # Find all citation markers in the sentence
            markers = self._citation_marker.findall(sentence)
            if markers:
                # Use the first one for simplicity, or we could duplicate the claim per marker
                results.append((sentence.strip(), int(markers[0])))
            else:
                results.append((sentence.strip(), None))
                
        return [r for r in results if len(r[0]) > 3]
