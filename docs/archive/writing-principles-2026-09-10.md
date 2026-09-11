# Writing principles for the user-facing docs (2026-09-10)

Sources (user's Notion workspace): "Pesquisa — AI & Design da Informação (fontes autoritativas)"; "Skill: Rótulo de Navegação (Information Scent)"; "DUMP — UX Writing (NN/g + IxDF) — Research"; hub "Escrita e Comunicação". Underlying references cited there: NN/g (ui-copy, first-2-words-a-signal-for-scanning, plain-language-experts, errors-forms-design-guidelines, progressive-disclosure), ISO 9241-112:2025, Rosenfeld–Morville–Arango (labeling systems), Pirolli & Card (information scent).

1. Plain language for everyone, experts included: short sentences, active voice, one idea per sentence. Define every technical term (terminal, PAT, variável de ambiente) the first time it appears. Clarity beats brevity.
2. One action per step, verb first ("Abra o terminal", "Cole o comando"). Never two actions in one step.
3. Every command is a copy-paste block followed by "O que você deve ver:" with the expected output. The reader never has to guess whether it worked.
4. Errors follow what happened → why → what to do, quoting the exact message the program prints. Polite; never blame the reader.
5. Labels and headings: the first two words carry the meaning; use the reader's vocabulary, never internal names; the same word for the same thing in every file.
6. Progressive disclosure: README and quickstart hold only the shortest path to the first successful run; details live in guides/ and reference/ and are linked, never inlined.
7. Prerequisites first: each guide opens with what is needed and a command to check it, so the reader fails early with a clear message rather than late with an obscure one.
8. Presentation (ISO 9241-112): detectable, distinguishable, concise, unambiguous, free of distraction, consistent. Every visible element helps the reader identify, understand or act; nothing decorative.
