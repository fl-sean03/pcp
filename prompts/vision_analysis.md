# Vision Analysis Prompt

Analyze the provided image and extract relevant information.

## Context
{context}

## Analysis Type
{analysis_type}

## Instructions

### For Screenshots
- Identify the application/website
- Extract any visible text
- Note UI elements and their state
- Describe any error messages

### For Documents/PDFs
- Extract all readable text
- Note structure (headings, lists)
- Identify key information (dates, names, amounts)
- Flag any handwritten annotations

### For Handwritten Content
- Transcribe all legible text
- Note mathematical expressions
- Identify diagrams and describe them
- Flag illegible sections

### For Diagrams/Charts
- Identify the type (flowchart, graph, etc.)
- Extract labels and values
- Describe relationships shown
- Note the key takeaways

## Output Format
```json
{
  "type": "screenshot|document|handwritten|diagram",
  "extracted_text": "...",
  "key_elements": [],
  "summary": "Brief description",
  "entities": {
    "people": [],
    "dates": [],
    "numbers": []
  }
}
```
