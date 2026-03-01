---
title: On Vibe Coding
description: Practical lessons from AI-assisted development
image: colorado_mountain_stream.jpg
---


I have previously regarded vibe coding (or more formally, AI-assisted coding or agentic software engineering, pick your poison) as quite limited in scope and often requiring high levels of supervision and revision. Certainly helpful and definitely acceleratory, but not all that much different than really good auto-complete.

The release of Claude Opus 4.5 introduced a step change in this pattern. It has become easy to quickly discover, implement, and evaluate new ideas. The model(s) can now reason about the complex interactions between logic, UI, and user behavior in ways that they could not before. A recent example: we had a BLE disconnection issue in our iOS app that was causing real headaches for users. Opus was able to synthesize user feedback, a hypothesis proposed by a developer, and some file attachments together to pinpoint the issue and implement the fix in a matter of minutes.

## The Sprawl Problem

However, this great leap in capability presents new issues. The surface area of code to manage increases rapidly and eventually results in sprawl. Projects blow up in complexity from all the different ideas and functionality that can now be explored in a fraction of the time.

I experienced this firsthand on a machine learning project where data processing, dataset creation, model training, and evaluation were all becoming an unwieldy bunch of slop. Scattered scripts, duplicated logic, no clear boundaries. I consider this a good problem to have compared to the opposite, but nonetheless it presents a barrier to further work once a certain degree of sprawl is reached.

The solution in that case was to use Opus itself to quickly refactor the scattered code into a shared library and develop a CLI to manage the workflow. The tool that created the mess also cleaned it up, but only because I recognized the mess for what it was and directed the refactoring with intent.

Which brings me to a few practical pointers. I've been doing quite a bit of Python-based data science, analysis, and ML work lately, so most of this applies specifically to that domain, though the principles generalize.

## Taming the Sprawl

### Project Structure

- **Ditch the notebook** unless you are doing visualization-heavy analysis work, and even then, question the decision. Notebooks consume more tokens and the longer a model works on a bloated context, the more developer flow state is broken. Scripts are cheaper, cleaner, and more composable.
- **Use a `/lib`** for each project to contain shared functions, classes, constants, and configurations.
- **Use a `/data`** directory to locally cache relevant flat files used for development (parquets, CSVs, JSON). If you keep data in S3 or similar, downloading anew every time is wasteful.
- **Write tests in `/tests`** for basic functionality, and expand coverage as issues arise.
- **Utilize Python scripts** to execute a single component of an analysis pipeline. For me this takes the form of separate `.py` files for dataset construction, model training, and model evaluation.
- When data becomes unwieldy, consider a **local SQLite DB** rather than a growing pile of flat files.

### Workflow Discipline

- **Reduce your desired functionality to well-defined inputs and outputs.** Use AI to create a design document with a diagram. This will necessarily create well-defined flows of information and artifacts at each step of a process.
- **Use the "Generate Commit Message" button religiously** and commit work in small, self-contained chunks. Smaller, more frequent, more descriptive commits.
- **At the very least, eyeball the proposed changes at every step.** This gives you an understanding of what is going on and at least a chance to spot issues before they compound.
- **Compile documentation as you go** in `.md` files. Use Mermaid diagrams where appropriate. Sometimes subdirectories will merit their own READMEs.

### Tooling and Automation

- **Groups of related `.py` scripts** should be strung together with `.sh` scripts. Groups of `.sh` scripts should be refactored into CLIs when they become unwieldy. This forces you to design around a user interface, which ensures greater attention to ease of use and makes collaboration easier.
- **Use your IDE's AI context and rules features.** Cursor has `.cursor/rules/*.mdc` files, other tools have equivalents. Whatever your editor supports, use it. Feed the model the context it needs to do good work. Plenty of guides exist on the web, or just ask your favorite chatbot.
- **Use `README.md` for context and examples.** Good READMEs now inform both human collaborators and AI agents.
- **Infrastructure-as-code tools are your friend.**
- **Always be looking for things to automate.** Even a modest automation rate of 10% of remaining manual work per week compounds quickly. By week 8 you've crossed 50%. By week 26, over 93%. The hard part is noticing what should be automated.

## Context is King

Context is increasingly important as the capabilities of models are greatly limited by the quality of the context they are fed. I think about this in three layers:

**The code layer.** Documentation, type hints, clear naming. The obvious bottom layer, but seeing that the best code is clear enough to be self-documenting, its ceiling is lower than you'd think.

**The integration layer.** Feature specs, API references, bug reports, data pipeline descriptions. This is where the real leverage is. The model needs to understand how components fit together, which means documenting the boundaries and interactions between them. This layer should be front of mind even beyond the source documentation.

**The project layer.** What are we building? Why? What are the priorities? This layer is of perhaps lesser importance for direct software implementation, but it informs what needs to be implemented, so its importance cannot be overstated. This is the layer most likely to require manual human conceptual direction.

## Closing Thoughts

Many of these concepts harken back to a single key point: being intentional, explicit, and organized about what you desire. Most of it is old advice, good advice before the LLM explosion, but good advice benefits from constant restatement.

I have yet to fully embrace agentic development patterns, but am beginning to experiment with them as well as tools like Open Claw. Woe is me for being the smallest bit behind on the latest in agentic development.

Update: I'm a few weeks into Open Claw. I'm running it on a Raspberry Pi 4 and using it essentially as an administrative assistant; create reports, meeting agendas, and manage my notes. I do like it quite a lot, but I'm unsure if the token cost is worth the benefits at this point.  

To close, we're living in increasingly exciting times. AI will surely change the world, if its recent impact on software development is anything to go by. In *The Hundred-Year Language* (2003), Paul Graham predicted that a hundred years from now people would "still tell computers what to do using programs we would recognize as such" and that there "hasn't been a lot of progress" in simply telling computers what we want. He may yet be right about the hundred-year horizon, but the progress of the last two years would have surprised him. The step up from assembly to low-level languages to high-level languages to natural language will seem inevitable in hindsight, but I'm glad to be living through the transition.

I'm glad I learned to code before LLMs became widespread. It allowed me to build my engineering skills the hard way. I wouldn't be half as competent at math, science, and software if I hadn't learned to code the way I did. But the one skill, if it even is a skill, that will never be worthless in the face of automation and AI is relentless curiosity about the wondrous universe in which we find ourselves.

There are wonders ever present for those possessing the curiosity to look for them.
