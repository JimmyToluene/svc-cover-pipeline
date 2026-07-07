# Phase 0 Notes — Mora Budget Tally and Items Pending Manual Verification

> **Status: confirmed (2026-07-03).** The user's spot-check passed with no discrepancies reported;
> `refs/mora_budget.tsv` is the invariant baseline from this point on.
> **⚠ 2026-07-05 addendum (see end of document): the audio actually sings only 20 lines; the bridge is not in the audio.**
> The remaining open questions from listening (line 11 靜 = shi-zu, line 16 方へ = ho-e, line 8 melisma)
> are counted per the v1 performance; if a mismatch turns up later during SynthV beat-matching,
> come back to fix the tsv and sync the lyric version.

## Counting rules

- One note = one mora; long vowels (chōon, ー), geminates (sokuon, っ), and the moraic nasal (hatsuon, ん) each count as 1; yōon (きゃ/チャ) count as 1.
- Counting basis: **the romaji bundled with v1 is authoritative** (it reflects the actual performance), not dictionary readings.
  Lines where the two disagree are listed separately in the table below.
- Repeated sections (lines 21/22/24) have no romaji in the source; they are counted the same as their first occurrence.

## Lines where the dictionary reading and the v1 performance disagree (counts follow the performance)

| Line | Position | Dictionary reading | v1 performance (romaji) | Impact on count |
|---|---|---|---|---|
| 2 | 1つ | ひとつ hi-to-tsu (3) | i-t-tsu「いっつ」(3) | None (both are 3), but the delivery itself needs listening confirmation |
| 11 | 靜 | しずか shi-zu-ka (3) | shi-zu (2) | Counted as 2; likely a truncated delivery, needs listening confirmation |
| 16 | 方へ | ほうへ ho-u-e (3) | ho-e (2) | Counted as 2, needs listening confirmation |
| 23 | 歩い続ながら | (ungrammatical) | a-ru-i-tsu-zu (5) | Counted as 8 per the performance (あるいつづながら); the Pass A fix 歩き続けながら adds +1 mora and needs a note-split plan |

Clear romaji errors (**no impact on mora counts**; all romaji is regenerated in v2):
u ga bu (→ ukabu, line 14), me gu ru (→ mekuru, line 13), cyaa ku (→ non-standard spelling, line 11),
wa su ra re zu (忘られず, archaic usage, kept for now and flagged as questionable).

## Candidate melisma / syllable-split spots (pay special attention while listening)

- Line 12「未来は」: the romaji is written ha (wa) — confirm it is sung wa.
- The「。」pauses in lines 6 / 17: confirm whether they are rests or held notes.
- The chorus lines (7/9/10) are all 13 morae; line 8 is 14 — confirm whether line 8 really has
  one more note than the other chorus lines, or whether there is a melisma (two morae squeezed into one note).

## Melody MIDI / project file search results (2026-07-03)

Overseas search engines turned up no publicly posted MIDI/project files for "Nian Zhang Shi"
(Bilibili's on-site content is poorly indexed). Recommendation: search from inside China yourself —
on Bilibili for "Nian Zhang Shi instrumental / MIDI / cover-tuning project", plus midishow.com and
5sing. If nothing turns up, fall back per CLAUDE.md Phase 4: run MDX-Net separation on
`refs/anon_version.mp3` (its vocal is an RVC dry vocal plus reverb, so separation is easy).
This does not block Phase 0/1.

## ✅ What you need to do (Phase 0 hard gate — cannot be skipped)

Count the notes line by line against `refs/anon_version.mp3`, spot-checking the following 6 lines
(chorus first), and confirm that "the line's note count == the mora count in the tsv":

1. Line 7「雪峰先生忘られず」— should be 13
2. Line 8「そっとそっと僕の手を繋ぐ」— should be 14 (key point: is there a melisma)
3. Line 10「勇気の全部君がくれた」— should be 13
4. Line 11「チャーク粉肩に乗る雪より靜」— should be 15 (key point: whether 靜 is sung as only two morae, shi-zu)
5. Line 16「逃げわず　その丘の方へ」— should be 11 (key point: whether 方へ is ho-e or ho-u-e)
6. Line 23「困難も　歩い続ながら」— should be 13

Criteria: sing along and count the notes; if a line's actual note count differs from the tsv,
write down "line number + actual count + where one syllable spans multiple notes or one note
carries multiple syllables", and I will update the tsv. Once everything is confirmed, Phase 0 is
complete and the tsv becomes the invariant baseline for all subsequent revisions.

## ⚠ Addendum (2026-07-05) — Structural discovery: the audio sings only 20 lines; the bridge and the chorus-2-only lines are absent

While building the subtitle timeline (Phase 4 v2 render), we found that the structure actually sung in `refs/anon_version.mp3` is:

- Verse A (1–6) → chorus (7–10) → verse B (11–16) → **chorus repeat (lines 7/8/9/10, original words)** → outro
- The bridge (17–20) from the v1 document and the chorus-2-only lines (**23, 25**) are **not in this audio**.

Three independent pieces of evidence (all reaching the same conclusion):

1. **RMS phrase segmentation**: the six phrase durations of the final section (134.4–162.5s),
   2.86/2.83/6.29/2.86/6.27/3.11s, match chorus 1 (59.8–87.9s),
   2.86/2.81/6.32/2.88/6.27/3.09s, one for one; total span 28.15s vs 28.09s.
2. **MFCC phoneme similarity**: chorus 1 vs final section = 0.838; control pair (chorus 1 vs an equal-length slice of verse B)
   = 0.359. The same melody with different lyrics does not reach 0.8+ — this is the same lyrics sung again (not an audio copy; waveform correlation is only 0.09).
3. **Adversarial ASR**: feeding the lyrics of lines 21–25 as the initial_prompt to faster-whisper
   large-v3-turbo and transcribing just the final section still outputs「雪峰先生忘られず。そっとそっと僕の手繋ぐ。
   雪峰先生…る。…の全部君がくれた」— the word order of chorus 1, including そっとそっと, which does not appear anywhere in lines 21–25.

**Impact and open decisions (user call required):**

- The claim in `docs/synthv_howto.md` that "386 notes trimmed to 342 to fit the 25 lines of lyrics" no longer holds:
  the reference audio only contains melody for 20 lines (about 283 morae plus ornaments). The melody of the bridge (17–20) and of lines 23/25
  has **no reference**.
- Option A: the final product follows the audio's actual structure (20 lines; lines 17–20/23/25 of final.md are not sung);
- Option B: find the full-length audio of BV139Gm6REz6 (the current mp3 may be a cut-down version), then redo separation + alignment;
- Option C: transcribe the bridge melody ourselves from the corresponding section of the original Chinese version (if that section exists there).
- The 25 lines transcribed verbatim into v1 are themselves unaffected (the Bilibili video's subtitles read that way); what is affected is only
  which lines this mp3 reference can support in terms of melody/timing.

The subtitle timeline (`refs/line_times.tsv`) has already been filled in per the actual 20-line structure, with the repeated section marked `7r/8r/9r/10r`.
