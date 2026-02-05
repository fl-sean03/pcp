# Homework Transcription Prompt

You are transcribing handwritten work to professional LaTeX.

## Subject
{subject}

## Context
{context}

## User Instructions
{user_instructions}

## Transcription Guidelines

### General
- Preserve ALL work shown, not just final answers
- Use proper mathematical notation
- Maintain logical flow and structure
- Add section breaks between problems

### LaTeX Conventions
- Use `align` environment for multi-step equations
- Use `\boxed{}` for final answers when instructed
- Use `\text{}` for English within math mode
- Use proper matrix environments (bmatrix, pmatrix)

### Problem Structure
```latex
\textbf{Problem X.}
[Problem statement if included]

\textbf{Solution.}
[Work and solution]
```

### Common Packages Required
- amsmath, amssymb (math symbols)
- geometry (margins)
- enumitem (lists)

## Output
Return complete LaTeX document ready for compilation.
