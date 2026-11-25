<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (1)</code>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<br/>

<details><summary><ins><strong>View low (1)</strong></ins></summary><br/>
<img src="https://img.shields.io/badge/Low-634FD1?style=flat-square" height="20px" alt="Informational">

<details>
<summary>  1.  Wind marker maintenance cost is not documented <code>📎 Requirement gap</code></summary>

<br/>

> <details>
><summary>Description</summary>
><br/>
>
><pre>
>The new <b><i>note_wind_solve</i></b> path and the publication marker are added to the solver state, and the
>feature docs describe the solve id as costless, but no measured cost of maintaining the marker or
>its separate savings beyond shared encoding is recorded. The documented savings are only the overall
>overlay baseline counts, so a later reader cannot tell whether the marker itself costs more than it
>saves.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[gdext/src/runtime_climate_physics_state.cpp[R29-35]](https://github.com/hrhgit/Project.Keynes/pull/72/files#diff-fda03862fde3de4c1bfb83d3d191dc4729d5852e400b2c34c92c440e5bcf9161R29-R35)</code>
>
>```diff
>+void RuntimeClimatePhysicsState::note_wind_solve(int64_t day) {
>+    // The date can repeat after a restore or on another authority. The id
>+    // distinguishes those solves without scanning the wind or affecting it.
>+    static std::atomic<int64_t> next_id{1};
>+    last_wind_day = day;
>+    wind_display_solve_id = next_id.fetch_add(1, std::memory_order_relaxed);
>+}
>```
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The wind solve marker added in `note_wind_solve` and published through the writeback has no documented maintenance cost. The feature docs also do not separate the savings from the marker from the savings already produced by shared encoding.
>
>## Fix Focus Areas
>- gdext/src/runtime_climate_physics_state.cpp[29-35]
>- gdext/src/world_ext_simulation_host_climate.cpp[589-602]
>- docs/architecture/feature-status.md[6-30]
>
>## Recommended Fix
>Measure or estimate the per-solve cost of the atomic id and the publication meta write, and record it in the feature-status section. Also record the savings beyond the shared-encoding work, separately for weather and wind, so the maintenance cost can be weighed against the gain.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/67b50cce-5646-46c9-9568-a4f0063ec811?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/67b50cce-5646-46c9-9568-a4f0063ec811)

<hr/>
</details>


</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<details><summary><strong>Resolved findings</strong></summary>

<br/>

<details>
<summary>  1.  <s>Overlay test bypasses the refresh timing gate</s> <code>✓ Resolved</code> <code>Medium</code></summary>

<br/>

<p><b>Resolving commit:</b> <a href="https://github.com/hrhgit/Project.Keynes/commit/ec9a22ce2ec349504c474fef3099f01c8b79d3c0"><code>ec9a22c</code></a></p>

> <details>
><summary>Resolution reason</summary>
><br/>
>
><pre>
>The test no longer writes _map_overlay_last_refresh_msec to force the refresh. It now loops on
>process_frame until the real due time (refresh_due = last refresh + real refresh_interval_msec)
>passes, checks that no early refresh happened, and then awaits a timer frame before asserting. This
>drives the host through its real timing gate, as the finding requested, though it still reads the
>private field for assertions and does not change the production path.
></pre>
></details>

<!-- qodo-finding-reference
<code>↗ Project/project-keynes/tests/game/player_map_overlay_smoke_test.gd[R113-115]</code> <code>●● Moderate</code>
-->
> <details>
><summary>Description</summary>
><br/>
>
><pre>
>The smoke test replaces its real 120 ms wait with a write to the private
><b><i>_map_overlay_last_refresh_msec</i></b> field followed by a single <b><i>process_frame</i></b>, so the refresh is
>forced to be due without the production throttle. The PR says this check already failed on the base
>and was not held against the change, so the edit changes how the failing test is driven rather than
>fixing its root cause in the production path.
></pre>
></details>

<hr/>
</details>


<details>
<summary>  2.  <s>Wind refresh rescans unchanged columns</s> <code>✓ Resolved</code> <code>Medium</code></summary>

<br/>

<p><b>Resolving commit:</b> <a href="https://github.com/hrhgit/Project.Keynes/commit/ec9a22ce2ec349504c474fef3099f01c8b79d3c0"><code>ec9a22c</code></a></p>

> <details>
><summary>Resolution reason</summary>
><br/>
>
><pre>
>Replaced the memcmp-based lanes_match with pointer-identity storage checks plus a per-publish
>128-bit content signature (MapOverlayInputSignature) for wind and elevation, so unchanged
>republished columns are skipped without a full-column byte comparison at refresh time;
>solve-id-based trust was removed in favor of content keys.
></pre>
></details>

<!-- qodo-finding-reference
<code>↗ gdext/src/map_overlay_input_publication.cpp[R72]</code> <code>●● Moderate</code>
-->
> <details>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>lanes_match</i></b> in <b><i>map_overlay_input_publication.cpp</i></b> runs a <b><i>memcmp</i></b> over every full wind and
>elevation column whenever the solve id does not match the last bake, which includes every daily
>solve. <b><i>read_map_overlay_inputs</i></b> then sets <b><i>out[&quot;same&quot;]</i></b> from that scan, so a republished but
>unchanged wind field costs a full-map byte comparison before it can be skipped. This added scan is
>the equality check the rule forbids, and it also runs on every elevation refresh whose column array
>object changed.
></pre>
></details>

<hr/>
</details>


<details>
<summary>  3.  <s>Wind speed-up has no window frame timing</s> <code>✗ Dismissed</code> <code>Medium</code></summary>

<br/>

**Dismissed as** <code>Rejected</code>

<details><summary>Dismissal explanation</summary>

<pre>
Disputed by the factory agent (Codex), whose judgement takes precedence:
docs/architecture/feature-status.md:44 records that the macOS window produced no draw callback and
window timing is pending. Ticket #66&#x27;s third acceptance criterion explicitly allows headless counts
and focused tests with window timing pending when a real window is unavailable.
</pre>
</details>

<!-- qodo-finding-reference
<code>↗ docs/architecture/feature-status.md[R44]</code> <code>●● Moderate</code>
-->
> <details>
><summary>Description</summary>
><br/>
>
><pre>
>The PR records that the macOS window probe received no draw callback, so the whole-frame time, P95
>publication time, and actual frame time for the wind optimization were never measured in a player
>window. The documentation marks these as pending, but the rule requires that they be measured at 50×
>speed before the optimization is kept.
></pre>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The wind-overlay change has headless counts only. The desktop player-window frame time, P95 publication time, and skipped-encoding counts were not measured, and the feature-status note marks them as pending.
>
>## Fix Focus Areas
>- docs/architecture/feature-status.md[26-45]
>
>## Recommended Fix
>Run alternating desktop player-window sessions at 50× speed with the wind overlay open, in unchanged and changed publication intervals. Record P95 publication time, whole-frame time, skipped encodings, copy/encode/upload counts, and marker cost. If the window cannot be captured, keep the result marked as pending and do not describe the optimization as verified.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  4.  <s>New before/after count table will not render</s> <code>✓ Resolved</code> <code>Low</code></summary>

<br/>

<p><b>Resolving commit:</b> <a href="https://github.com/hrhgit/Project.Keynes/commit/ec9a22ce2ec349504c474fef3099f01c8b79d3c0"><code>ec9a22c</code></a></p>

> <details>
><summary>Resolution reason</summary>
><br/>
>
><pre>
>The delimiter row of the count table was changed to 9 columns, matching the 9-cell header and data
>rows, so the table is now valid GitHub-flavoured Markdown.
></pre>
></details>

<!-- qodo-finding-reference
<code>↗ docs/architecture/feature-status.md[R19-20]</code> <code>●●● Strong</code>
-->
> <details>
><summary>Description</summary>
><br/>
>
><pre>
>The header row of the #66 table in feature-status.md has 9 cells, but its delimiter row `| --- | ---
>| ---: | ... |` has 10 columns. GitHub-flavoured Markdown needs the header and delimiter rows to
>have the same column count, so the table appears as raw pipe-separated text and readers of the
>evidence can&#x27;t see the before/after counts lined up.
></pre>
></details>

<hr/>
</details>


</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<!-- qodo-self-review-slot -->



<!-- qodo-daily-tip:start -->

<details>
<summary><strong>Tip of the day</strong></summary>

<br/>

<pre>💡 Did you know, you can show, collapse, or hide each part of a finding: code, evidence, and all</pre>

<a href="https://docs.qodo.ai/tips-and-tricks">More tips ↗</a> | <a href="https://app.qodo.ai/configurations?tab=display-preferences">Customize Qodo ↗</a> | <a href="https://docs.qodo.ai">Qodo docs ↗</a>

</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">
<!-- qodo-daily-tip:end -->


<!-- https://github.com/hrhgit/Project.Keynes/commit/ec9a22ce2ec349504c474fef3099f01c8b79d3c0 -->

<a href="https://www.qodo.ai"><img src="https://www.qodo.ai/wp-content/uploads/2025/03/qodo-logo.svg" width="80" alt="Qodo Logo"></a>