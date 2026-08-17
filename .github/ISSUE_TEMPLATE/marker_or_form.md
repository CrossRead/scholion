---
name: A marker or a lab form is not recognised
about: The dictionary does not know a test, or a form is parsed wrongly
title: ''
labels: dictionary
assignees: ''
---

<!--
  ⚠ DO NOT ATTACH THE FORM ITSELF. A lab PDF is a medical document with your
  name, your date of birth and your results on every page. What is needed here is
  the SHAPE of one row, not your row — invent the numbers, keep the layout.

  Right:  «Глюкоза            5,4      3,9 - 6,1     ммоль/л»
  Wrong:  a screenshot, an attached PDF, or a real line copied from your form.
-->

**The test** — its name as the form prints it, and in which language:

**One row, with the numbers replaced by invented ones**, keeping the spacing:

```
```

**What the application did** — did not recognise the row / took the wrong number /
put it under another marker:

**The unit as printed on the form**, and the reference range beside it:

<!--
  If you already know the key you expected, name it: `scholion markers` lists the
  ones in your profile, and the dictionary lives in
  src/scholion/knowledge/lab_markers.json — a new name for an existing marker is
  a two-line change under `labels.<language>.names`.
-->
