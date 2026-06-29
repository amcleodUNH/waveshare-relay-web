# From Conversation to Control: A Case Study in Domain-Expert-Driven Code Generation, with a Proposed Specification Pattern

**Author:** A. McLeod
**Development assistant:** Claude (Anthropic), Claude Code
**Artifact:** `waveshare-relay-web` - <https://github.com/amcleodUNH/waveshare-relay-web>

---

## Abstract

This is the story of a small piece of working software and what its making taught me. The artifact is a zero-dependency web control panel for an eight-channel Waveshare *Modbus POE ETH Relay* board, built for an uncrewed surface vehicle (USV); the unusual part is that it was produced entirely by talking to a large-language-model coding agent, without the human author writing a line of source. I am a field practitioner, not a programmer: my knowledge is of the device and its use, not of sockets and front-ends. I treat the project as a case study with two threads. The first is technical, and turns on a single non-obvious fact: although the board advertises Modbus and listens on the Modbus port, it does not speak Modbus-TCP at all but a serial dialect (Modbus-RTU) wrapped in TCP, a distinction that quietly defeats off-the-shelf clients and that the agent settled only by probing the hardware directly. The second thread treats the conversation itself as data. I classify each of the eleven exchanges by what it was actually doing, then ask a counterfactual: which corrections could a better opening request have prevented, and which were irreducible? From the answer I abstract a lightweight prompting pattern, the Domain-Expert Specification (DES) schema, meant to help practitioners who know their gear but not their compiler get to a correct artifact in fewer passes, and I give a single-pass reconstruction of this very project to show what that looks like. I also put numbers on effort: the AI-coupled work delivered a tested, hardened, published tool in about an hour of active attention, against a three-point (PERT) estimate near 25 person-hours (roughly 20 to 30) for an unaided professional, and a larger or simply infeasible burden for a non-programmer working alone. This is one case, observed and not controlled; the schema is a hypothesis rather than a validated method, and the durations are an instrumented bound set beside a modeled estimate.

**Keywords:** code generation, large language models, human-AI interaction, requirements specification, Modbus, industrial control, end-user programming.

---

## 1. Introduction

There is a familiar bottleneck in instrumentation work. The person who understands a device best is often a field engineer, a marine technician, or a bench scientist, not a software developer; and that person, however fluent with the hardware, usually cannot write the software glue that turns a capable box into a usable tool. The standard fix is to hand the job to a programmer, which adds cost, delay, and a translation gap between what the domain expert means and what the code ends up doing.

Coding agents change the shape of that bottleneck, and this paper looks closely at one instance of the change. A practitioner (me) specified an operational tool in plain language, and an agent built it, found and fixed its own bug, hardened it, packaged it, and published it. My aim here is twofold. First, I want to record the artifact honestly, including the one piece of engineering that was genuinely hard, namely the board's quiet departure from the Modbus-TCP standard. Second, and I think more usefully, I want to read the transcript as evidence: to sort my own inputs by what they accomplished, separate the corrections a sharper opening request could have avoided from the ones nothing could have avoided, and distill a reusable way of asking for people in my position.

---

## 2. The device, and the protocol it does not advertise

The Waveshare *Modbus POE ETH Relay* is an eight-channel relay board with Power-over-Ethernet and an RJ45 jack. It bills itself as Modbus-capable and listens on TCP port 502, the registered Modbus port, so the natural assumption is that it speaks Modbus-TCP, in which each request carries a seven-byte MBAP header and drops the checksum that the serial protocols use.

The natural assumption is wrong, and probing the board is what showed it. Standard Modbus-TCP requests opened a socket cleanly and then went nowhere; reads timed out no matter which unit identifier we tried. Send the board a raw Modbus-RTU frame instead (`address, function, data..., CRC16`, the framing native to an RS-485 serial line) and it answers at once. The board is, in plain terms, a transparent bridge: it shovels the socket's bytes straight to the serial engine inside it, unchanged. Two of the exchanges that pinned this down, with the CRC bytes left off for readability:

- `01 01 00 00 00 08` (FC 0x01, Read Coils, eight coils from 0x0000) returned a one-byte bitmap, confirming eight channels, all off.
- `01 03 40 00 00 01` (FC 0x03, Read Holding Register 0x4000) returned `00 01`, the board's configured Modbus address.

Switching a relay uses FC 0x05 (Write Single Coil): `0xFF00` closes it, `0x0000` opens it, and a vendor-specific `0x5500` toggles it; coil address `0x00FF` hits every channel at once. Those few primitives, wrapped in RTU framing over a TCP socket, are the whole control surface the tool needs.

I dwell on this because it is the project's one piece of non-obvious knowledge, and because of what it implies for the rest of the paper. I could not have told the agent this up front, since I did not know it; nobody knew it until the board was poked and watched. It had to be *discovered*, by trying things and reading the replies, and discovery of that kind is a capability no amount of careful wording on my end can replace.

---

## 3. The artifact

What we ended up with is a single Python file (`relay_control.py`) that leans only on the standard library, a deliberate choice that keeps deployment painless on whatever host is bolted into a vehicle. It does two jobs. One layer talks to the board in its serial dialect: a CRC-16, frame construction for the read and write function codes, and a transaction routine. In its final form (see §4, turn 10) this layer holds a single persistent, lock-guarded socket and reads each reply by length-framing it per function code, so a reused stream cannot fall out of step. The other layer stands up a `ThreadingHTTPServer` that serves a server-rendered control page and a small JSON API (`GET /api/status`, `POST /api/control`). The page gives one card per channel, with on, off, toggle, a live switch, and a momentary pulse you can set in seconds, plus all-on and all-off across the board; it polls state every two seconds and shows a dot that goes green when the board is answering (Figure 1).

![Figure 1. The web control panel, channels 1, 2, and 5 energized.](relay-panel.png)

*Figure 1. The generated control panel rendering a mixed channel state.*

---

## 4. The interaction as method

The tool came together over eleven user turns, and the shape of those turns is the interesting part. Table 1 condenses each input and labels it by what it was doing. I distinguish *specification* (states a requirement), *authorization* (grants permission), *defect report* (flags a fault), *feature* (adds scope), *packaging* (distribution and structure), *deferral* (marks a value as later-bound), *context* (supplies domain framing), and *constraint* (bounds how the work is done).

**Table 1. The development interaction, by turn.**

| # | User input (condensed) | Function | Elicited |
|---|------------------------|----------|----------|
| 1 | Waveshare Modbus POE ETH relay at 172.30.0.200; build a script for operational control via a custom webpage | Specification | Initial system; protocol discovery |
| 2 | The device is unconnected; relays may be activated for testing | Authorization | Live switching verification |
| 3 | The provided web GUI does not operate the relay board | Defect report | Diagnosis and fix of a front-end fault |
| 4 | Add the momentary-pulse buttons to the cards | Feature | Per-channel pulse control |
| 5 | Create this as a new project on my GitHub account and prepare for publishing | Packaging | Repository, README, license, push |
| 6 | "Do both" (accept proposed cleanup and security hardening) | Packaging | Loopback default; tree cleanup |
| 7 | Channel labels will be changed later during install/testing on the USV | Deferral + Context | Placeholder labels; USV framing |
| 8 | This should be a separate project from Starlink; move it parallel and isolate it | Packaging (structural) | Sibling directory; isolated memory |
| 9 | Add a GUI graphic to the GitHub project | Packaging (docs) | Rendered screenshot asset |
| 10 | Do this (a reliability refactor) without connection to the board | Constraint + Reliability | Persistent-connection client; hardware-free verification |
| 11 | Write this paper | Meta | The present document |

Two of these turns deserve a closer look, because they sit on opposite sides of an important line: the difference between a defect of *specification* and a defect of *implementation or knowledge*.

**Turn 3, a defect report.** The first web page rendered but would not throw a relay. The cause was a bug the agent had written into its own first draft: the page assembled its controls with inline `onclick` handlers built by JavaScript string concatenation, embedded inside a Python triple-quoted string, and Python quietly collapsed the escaped quotes into a JavaScript syntax error that killed the whole script. The fix was to render the cards server-side and dispatch clicks by `data-` attribute delegation. No wording of my request could have headed this off; it was a flaw in the build, not a gap in the ask. What is worth noting is that my report did not need to be clever. "Does not operate the relay board" was enough to send the agent back to find and fix the thing. I did not need to know why, only that it was wrong, which is exactly the judgment I do have.

**Turn 10, reliability under a constraint.** While we were grabbing the screenshot, the board went fully dead, stopped answering even a ping, after a burst of overlapping connections from the two-second poller, my test commands, and some direct reads all arriving at once. The cause was architectural: the client opened and closed a fresh TCP socket for every transaction, and these bridges keep a very small connection pool that rapid open-and-close churn can exhaust, wedging the device until it is power-cycled. I asked for a rebuild *with the board offline*, since it was offline anyway and on a vehicle the link will drop for real. The agent rewrote the client around a single persistent socket and proved it against a synthetic Modbus server that imitated the board's coils and its one-connection-at-a-time behavior, confirming that the connection is held and reused, that it reconnects cleanly after a dropped link, and that eight threads hammering it at once do not scramble the stream. I like this turn for two reasons: the requirement *emerged* from breaking the thing under load, the way you learn the real limits of any gear, and the verification was done with no hardware at all, by modeling the board and testing against the model.

---

## 5. Reading the inputs: what could have been said sooner

Here is the paper's central question. Of the eleven turns, some were genuinely generative or could not have come earlier, while others were corrections that a fuller opening request would have pre-empted.

**The irreducible ones.** Turn 1 (the seed request) and turn 11 (this paper) are required by definition. Turn 3's defect was an implementation bug rather than a missing requirement, and it could only surface once the artifact existed and was watched. The protocol discovery behind turn 1 was irreducible in the same spirit: it rode on runtime evidence I did not have.

**The avoidable ones.** Turns 4, 5, 6, 8, 9, and arguably 10 each supplied something that was in my intent from the start but only got said once its absence was staring at me:

- The momentary pulse (turn 4) is a routine relay operation on a USV, for instance pulsing a latching actuator or a reset line; leaving it out of turn 1 under-described what the tool needed to do.
- A real, separate, published, documented project (turns 5, 8, 9) was where this was always headed; the opening request said only "a script."
- Surviving connection exhaustion (turn 10) follows from the destination. An unattended boat implies a flaky, long-lived link, and that could have been stated as a non-functional requirement on day one.

**A single-pass reconstruction.** Fold the realized intent back into the seed, and you get a request that, setting aside the irreducible protocol discovery and the chance bug, could have produced substantially the final artifact in one go:

> *Build a standalone, publishable tool to operate a Waveshare Modbus POE ETH Relay (8-channel) at 172.30.0.200 over Ethernet. The device is on the bench and unconnected, so you may switch relays to verify. I am not a programmer; deliver a single self-contained program I can run with minimal setup, plus a browser control panel exposing, per channel, on/off, toggle, and a momentary pulse of configurable duration, and global all-on/all-off. The board is destined for an uncrewed surface vehicle, so it must tolerate an unreliable, long-lived network connection without wedging the device. Channel names are unknown until install; leave them as editable placeholders. Verify behavior; where hardware is unavailable, verify against a model. Package it as its own public GitHub repository with a README, an open-source license, and a screenshot, kept separate from my other projects.*

I do not offer this as a reproach to how the real conversation went; discovering your own requirements as you go is normal, and often the efficient thing to do. I offer it as evidence that a sizable share of the turns were latent in the first intent, and so, in principle, could have been hoisted to the front.

---

## 6. A pattern worth proposing: the Domain-Expert Specification (DES) schema

Generalizing from §5, I propose a lightweight schema for people who know a device and its field use but not programming. Its premise is simple: such users reliably hold exactly the information an agent most needs and most often lacks, and asking for it on purpose turns that tacit knowledge into specification. The schema has seven slots.

1. **Device and interface.** What the hardware is, its addressing, and how you reach it (here: a named board, an IP, an Ethernet/PoE link). *You know this precisely; it points the agent in the right direction and bounds the protocol hunt.*
2. **Operational repertoire.** Every action you expect to perform, in field terms (on, off, toggle, pulse, all-channels). *This is the slot I shorted at turn 4, and it is the one you are best equipped to list completely, because it is just your hands-on routine written down.*
3. **Field context and deployment.** Where and how the tool will live, a bench fixture versus an unattended vehicle being different animals. *This slot licenses the non-functional requirements; "uncrewed surface vehicle" implies the reliability fix of turn 10.*
4. **Authorization and safety envelope.** What the agent may do to verify, and what it must not (here: relays may be switched because nothing is connected). *Explicit permission unblocks empirical verification, which is otherwise held back for safety.*
5. **Deferred parameters.** Values you do not yet know and want left configurable (the channel labels, finalized at install). *Naming the deferral heads off a premature, wrong guess and a later correction.*
6. **Deliverable and distribution.** The form and destination you actually want (a single runnable program; its own public, documented repository). *Stated first, this slot collapses turns 5, 8, and 9 into the opening pass.*
7. **Verification expectation.** The standard of evidence you require, including the fallback when hardware is absent (verify live; otherwise verify against a model). *This turns "make it work" into a checkable obligation and legitimizes model-based testing.*

You need not write code, nor know Modbus from MQTT; the schema asks only for what you already hold. And it deliberately leaves out implementation: not how to frame the protocol, not how to build the page, not how to handle the connections. Those (turns 1 and 3) belong to the agent and to discovery, and they are exactly the things you do not want to be specifying.

A reusable template:

> **Device and interface:** _<what it is, address, how reached>_
> **I need to:** _<every action, in field terms>_
> **It will be used:** _<where and how it is deployed; reliability or environmental demands>_
> **You may, to test:** _<permitted verification actions and prohibitions>_
> **Not yet known (leave configurable):** _<deferred parameters>_
> **Deliver as:** _<form, packaging, where it should live, docs and license>_
> **Verify by:** _<evidence required; fallback when hardware is absent>_
> **About me:** _<relevant non-coding expertise; coding experience>_

---

## 7. How long it took, and how long it might otherwise have taken

A question this study can partly answer is how the *duration* of conversational, AI-coupled work compares with the conventional, unaided kind for the same artifact. I treat duration as effort (person-hours), not calendar time. The project's wall-clock span ran to several days, but that span was mostly idle stretches waiting on my own availability and review, not generation work, and an unaided developer's calendar would be just as punctuated. Effort is the quantity worth comparing.

### 7.1 Method

For the AI-coupled side I bound active effort from the record. The tool was built and revised across eleven short turns and the agent's bounded replies, with version-control timestamps showing successive increments landing minutes apart: the first build and its security-hardening revision six minutes apart, the screenshot and the persistent-connection rebuild eleven minutes apart. Active effort, meaning agent generation plus my own reading and direction, comes to about an hour. I report it as an order-of-magnitude figure and round up on purpose, since the interaction was never instrumented for precise timing and I would rather overstate the human-side cost of reviewing output than understate it.

For the unaided side there is nothing to measure, because no parallel human build happened, so I estimate it instead. I break the artifact into eight work components, give each a three-point estimate (optimistic *a*, most-likely *m*, pessimistic *b*), and apply the PERT approximation: expected effort *t*ₑ = (*a* + 4*m* + *b*)/6, with standard deviation *σ* = (*b* − *a*)/6, treating the components as independent so the total variance is the sum of the component variances. The estimates assume a competent professional developer, which is a generous baseline given that the person who actually directed the work calls himself a non-programmer (more on that shortly). Scope is matched to what was delivered: discovery, testing, hardening, and packaging are all in, not just the happy-path code.

### 7.2 Result

**Table 2. Three-point (PERT) effort estimate for an unaided professional build.** All values in person-hours.

| Work component | *a* | *m* | *b* | *t*ₑ | *σ* |
|----------------|----:|----:|----:|-----:|----:|
| Protocol discovery (identify RTU-over-TCP, unit ID, function codes) | 1.0 | 3.0 | 10.0 | 3.83 | 1.50 |
| Modbus client (CRC-16, frame build, transaction, decode) | 1.0 | 2.5 | 6.0 | 2.83 | 0.83 |
| Web server + JSON API (stdlib `http.server`) | 1.0 | 2.0 | 5.0 | 2.33 | 0.67 |
| Front-end UI (HTML/CSS/JS, cards, polling, pulse) | 2.0 | 4.0 | 9.0 | 4.50 | 1.17 |
| Integration debugging | 1.0 | 3.0 | 8.0 | 3.50 | 1.17 |
| Reliability hardening (persistent connection, framing, reconnect) | 1.0 | 3.0 | 8.0 | 3.50 | 1.17 |
| Testing + hardware-free mock server | 1.0 | 2.5 | 6.0 | 2.83 | 0.83 |
| Packaging & publishing (repo, README, license, screenshot) | 0.5 | 1.5 | 4.0 | 1.75 | 0.58 |
| **Total** | | | | **25.1** | **2.9** |

The components add up to an expected 25.1 person-hours with a standard deviation of 2.9 h (the total *σ* is the root-sum-square of the component values); a normal approximation puts a 90% interval at roughly 20 to 30 hours, about three working days. The biggest and shakiest line is protocol discovery: an unaided developer, without the agent's quick probe-and-watch loop, has to work out on their own that the board speaks Modbus-RTU-over-TCP rather than Modbus-TCP, the same fact the agent established empirically in §2.

### 7.3 Comparison

Set against that baseline, the AI-coupled work produced a tested, hardened, published artifact in roughly one hour of active effort, an effort reduction on the order of 20 to 30 times relative to an unaided professional. The comparison is sharper, though harder to quantify, against my *actual* alternative. I am not a professional developer; for me, building this unaided is not 25 hours but a different regime altogether, one that starts with acquiring socket programming, Modbus framing, concurrency, and front-end skills before the real work begins. The honest outcomes in that regime are some multiple of the professional estimate, or non-completion, which carries a real and non-zero probability that a tidy person-hour figure simply does not capture. So the operative comparison for someone like me is not "one hour versus twenty-five" but "a working tool versus, quite possibly, none."

### 7.4 Threats to validity

The AI-coupled number is an uninstrumented order-of-magnitude bound; the unaided number is a modeled estimate, not a measurement, and three-point estimates are well known to drift with whatever the estimator anchors on. Both rest on n = 1. The professional baseline could be conservative or generous depending on how familiar the developer already is with Modbus and with this board's odd framing; I widened the pessimistic protocol-discovery bound to soak up some of that. Most important, an effort ratio from one small artifact should not be stretched to large systems, where coordination, architecture, and years of maintenance dominate and a conversation will not carry you. These figures describe the small, single-purpose instrumentation tools where the method looks most advantageous, and not much beyond.

---

## 8. Discussion

A division of labor showed up here that the DES schema is meant to formalize. The practitioner brings the *what* and the *why*: the device, the job, where it is going, what it must never do, what "done" looks like. The agent brings the *how*: protocol framing, interface construction, concurrency and reliability engineering, and, just as much, the *discovery* of facts that can only be learned at runtime. The two corrective turns that no specification could have prevented, the board's hidden dialect and the bug the agent wrote itself, both fall squarely on the agent's side of that line, which is just where the schema's refusal to ask users for implementation would put them.

Three caveats keep me honest. First, this is one observed case, n = 1, with no control condition and an agent-and-user pair I cannot claim is representative; the schema is a hypothesis, and its supposed reduction in passes is untested. Second, some of what looks like under-specification is really good practice: working incrementally lets you defer a decision until an artifact makes the trade-off concrete, and I could not easily have judged the need for a persistent-connection design before watching the board wedge. A schema that front-loads every decision risks demanding commitments the user is not yet ready to make. Third, the schema assumes an agent that can actually do empirical discovery and model-based verification; against a weaker system, slots 4 and 7 would give back less.

Future work should test the schema head to head: paired tasks with and without the structured prompt, across several domain users and devices, measuring turns to acceptance, defect counts, instrumented development time against matched unaided controls, and the share of corrections that trace to specification gaps versus implementation faults.

---

## 9. Conclusion

A field practitioner produced, debugged, hardened, and published an operational device-control application by conversation alone, leaning on domain knowledge rather than programming skill. The interaction compressed development effort by roughly an order of magnitude against an estimated unaided professional baseline (§7) and, for a non-programmer, plausibly made the difference between a working tool and none. Reading the transcript back, I found that about half of its turns supplied requirements that were latent in the original intent and so could have been hoisted into a single pass, while a minority, the runtime protocol discovery and the generated bug, were irreducible and properly the agent's to carry. I gathered the hoistable part into the Domain-Expert Specification schema, a seven-slot prompt that asks practitioners only for what their expertise already supplies and keeps implementation detail off their plate by design. I offer it as a testable pattern for making domain experts effective directors of code-generating agents, and the tool itself as a small existence proof that the division of labor it encodes actually works.

---

### Materials and reproducibility

The complete artifact, including the persistent-connection client, the web layer, and the figure reproduced here, lives at <https://github.com/amcleodUNH/waveshare-relay-web> under the MIT License. The non-functional behavior described in §4 (connection reuse, reconnection, concurrency safety) was checked against a synthetic Modbus-RTU-over-TCP server emulating the board's coils and its single-connection semantics, with no physical hardware connected.

### A note on authorship

The software artifact and a draft of this paper were generated by an LLM coding agent (Claude, Anthropic) under the direction of the human author, whose inputs, reproduced and analyzed in §4 and §5, were the specification. The paper's self-referential reading of those inputs should be taken with that provenance in mind.
