# OpenMontage

**MANDATORY: Read `AGENT_GUIDE.md` before responding to ANY user message.**

Do not act on the user's request until you have read AGENT_GUIDE.md.
It contains routing rules that determine your first action based on what the user asked.
Skipping it WILL cause you to take the wrong action.

There are no instructions in this file. All instructions are in AGENT_GUIDE.md.


<claude-mem-context>
# Memory Context

# [OpenMontage] recent context, 2026-09-14 8:40pm GMT+2

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (19,380t read) | 769,135t work | 97% savings

### Sep 14, 2026
28669 5:28p 🔵 Checkpoint Protocol Architecture for OpenMontage Pipeline
28671 5:29p 🔵 Pipeline Manifest Architecture with 13 Pipeline Types
28672 " 🔵 Backlot Project Discovery via Glob and Marker Files
28673 " 🔵 Project Initialization Creates Canonical Subdirectory Layout
28674 " ✅ Project Registration: optimy-cuelgo Initialized in Backlot
S5511 Session resumption checkpoint: Document optimy-cuelgo project state and prepare for continuation after context restart (Sep 14 at 5:31 PM)
28675 5:33p ✅ Session Memory Created for optimy-cuelgo Project Resumption
S5512 Resume optimy-cuelgo campaign work and resolve empty Backlot project board by backfilling checkpoint records (Sep 14 at 5:33 PM)
S5513 Add dynamic camera moves and visual interest to static ad edit composition; subagent spawned to implement punch-in cuts, continuous micro-motion, segment transitions, and cutaway insert (Sep 14 at 5:36 PM)
S5514 Review draft video with dynamism improvements (punch-in cuts, transitions, SFX) and seek user feedback on zoom levels, text choices, and visual overlaps before final render (Sep 14 at 5:39 PM)
28681 5:41p 🔵 Audio SFX inventory and loudness levels documented
28682 " ✅ SFX assets bundled into project with credits
28683 5:42p ✅ Camera animation wrapper and empty ad-slot cutaway styles added
28684 " ✅ Video footage wrapped in camera animation containers and SFX layer integrated
28685 " 🟣 Complete multi-camera animation choreography with transition effects and impact timing
28686 5:48p ✅ Hyperframes snapshots regenerated with Gemini analysis
28687 5:49p ✅ Draft preview MP4 rendered successfully
28690 5:53p 🔵 Draft video output verified with specific technical specs
28691 5:54p 🟣 Dynamism rework completed on optimy-cuelgo edit with motion and SFX
28692 " 🔴 hyperframes snapshot reads GEMINI_API_KEY from repo .env, making paid calls even if shell key is unset
28693 " 🔵 Critical rendering constraint: --experimental-fast-capture=false required to preserve zoom tweens
S5516 User requested tight cut (v3) of Optimy "Ni de coña" ad with pauses removed to compress 40s timeline to ~28s (Sep 14 at 5:54 PM)
28694 7:32p 🔵 Silence detection analysis on avatar video clips
28695 " 🔵 Hyperframes-core editing recipe patterns for video composition
28696 " ✅ Opened Instagram reference post in browser
28697 " 🔵 Reference Instagram post analyzed: AvatarHype multi-accent avatar demo
28698 7:35p ✅ Backup of v2 composition before re-cut
28699 " ✅ Composition duration reduced from 40s to 28.11s
28700 7:36p ✅ Jump-cut restructuring of clip2 and clip3
28701 " ✅ SFX timing synchronized to jump-cut structure
28702 " ✅ Voice audio split and repositioned for jump-cut structure
28703 7:37p ✅ Caption timeline remapping for jump-cut composition
28704 7:38p ✅ GSAP timeline animation restructured for jump-cut composition
28708 7:42p ✅ Optimy ad v3 tight cut rendered with pauses removed
S5517 End card copy update and composition validation for Optimy v3 tight cut ad (Sep 14 at 7:42 PM)
28709 7:43p 🔵 End card animation structure in main edit HyperFrames project
28710 " ✅ End card tagline updated to focus on monthly creative production
28711 " 🔵 HyperFrames composition validation passed after end card text change
S5518 Compress Andromeda B-roll from 10s to 6s and integrate into main edit with fixes (Sep 14 at 7:43 PM)
28712 " 🔵 B-roll voiceover structure analyzed: two silence gaps and three-beat composition identified
S5519 Extract prompts and techniques from Avatar Hype Academy's "Biblioteca de Prompts" and create a reusable skill for realistic AI UGC avatar image and video generation (Sep 14 at 7:44 PM)
28713 7:45p 🔵 Voiceover loudness profiling reveals beat boundaries and silence characteristics
28715 7:49p 🔵 Hyperframes render job completed successfully for draft-v4.mp4
28716 8:02p 🔵 Successfully extracted prompts from Avatar Hype Academy biblioteca-prompts page
28717 8:03p 🔵 Extracted full structured resource library from Avatar Hype Academy biblioteca-prompts page
28718 " 🔵 Systematically extracted detailed prompt categories from biblioteca-prompts resource library
28719 8:04p 🔵 Extracted complete modular prompt assembly system and component library
28720 " 🔵 Extracted assembly workflows and multi-person video format instructions
28721 " 🔵 Examined project skill system architecture and APIMart skill structure
28722 8:05p 🟣 Created ugc-avatar-realism skill with complete prompt-building system for realistic AI UGC videos
28723 " ✅ Integrated ugc-avatar-realism skill into project video and image generation tools
28724 8:06p 🔵 Verified ugc-avatar-realism skill integration with passing test suite
28725 " ✅ Created ugc-avatar-realism-skill reference documentation in project memory
S5520 Integrate licensed Avatar Hype Academy course prompts into OpenMontage UGC avatar skill while respecting copyright constraints (Sep 14 at 8:07 PM)
28726 8:18p ✅ Documented optional external reference for licensed course prompts
28727 " ✅ Configured gitignore for licensed course material storage
28728 8:39p 🔵 UGC Avatar Realism Reference Document Verified
28729 " 🔵 UGC Avatar Realism Reference Document Structure and Prompt Content Mapped
28730 8:40p 🔵 Content Coverage Gaps Identified in UGC Avatar Reference Document
S5521 Verify and audit UGC avatar realism reference document; identify content coverage and gaps versus source material (Sep 14 at 8:40 PM)
**Investigated**: Examined `.agents/skills/ugc-avatar-realism/references/avatarhype-biblioteca.md` (220 lines, 13.7 KB). Performed content audits: checked file existence, git ignore status, document structure (headings), section markers, regional accent coverage, camera techniques, product categories, and lifestyle/setting scenarios. Compared findings to known web source version (~39.5 KB).

**Learned**: Reference document is a partial/abbreviated copy of the web source. Contains three main sections (Imagen, Vídeo, Formatos) with 48 example prompts. Covers basic camera techniques (zoom, orbit, handheld, slow-motion), multiple Spanish regional accents (Peninsular/Madrid, Rioplatense, Colombian, Mexican, neutral Latin American), and core production formats. File is properly git-ignored and excluded from version control. Significant content gaps exist: character sheet (3×3) missing, voice presets severely limited (2 lines vs. web's age/gender matrix), no fashion/skincare special actions section, gesture/action list incomplete (missing sofa, cooking, reading scenarios), animated content absent.

**Completed**: Content audit completed. Document structure and coverage mapped. Gap analysis performed against web source version. Identified 13.7 KB file contains approximately 35% of web version content (~39.5 KB).

**Next Steps**: Append missing sections from web source to local reference file using `>> .agents/skills/ugc-avatar-realism/references/avatarhype-biblioteca.md`. Sections to add: character sheet template (3×3), expanded voice presets (age/gender matrix), fashion and skincare special actions, complete gesture and lifestyle action library, animated content section. Use paste buffer method: `pbpaste >> [file]`.


Access 769k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>