# Talking a Relay Board Into Working

### How I built a piece of field software without writing a line of code, and what I make of that

**Andy McLeod**

---

---

## A short foreword

The best part of this line of work is that you never quite know how to handle what's sitting on the bench when you walk in. Proverbially speaking. Most days it's a varied repeat of something you've done before, which is fine because that's how you build the training and the scars. But every so often the job in front of you is genuinely new, and you get to fall back on what the old hands call the Survivor's Law: Adapt, Improvise, Overcome.

This is an account of one of those days, except the new thing wasn't a sonar mount, or telemetry toy but a slick new device to be investigated. I needed a control program for an off the shelf relay board bound for one of our autonomous surface vehicles, and instead of writing it - I'm not a programmer and never have been - I talked an AI coding agent through it, start to finish. We ended up with a tested, hardened, published tool. I want to set down what happened, because I think the how matters as much as the what, and there's a lesson in it for anyone in my position: people who know their gear and their field but couldn't write a socket handler to save their lives.

---

## 1. What I was after

The hardware was a Waveshare Modbus POE ETH Relay — eight channels, Power over Ethernet, sitting on the desk ad-hoc’d to the laptop on IP 172.30.0.200. Eventually it goes to an ASV to switch real equipment. What I wanted was simple to say and, it turns out, not so simple to do: a way to flip those relays from a web page. On, off, and the things a field setup actually needs. That was the whole of my opening request. As usual, I left out half of what I really wanted, because you don't know you wanted it until you see it isn't there. More on that.

---

## 2. The thing the board doesn't tell you

Here's where the first real lesson came, and it's the kind that would have cost me days on my own. Or brought the project to a stop.

The board says Modbus. It listens on port 502, which is the Modbus port. Any sensible person assumes it speaks Modbus-TCP - the modern, networked flavor, with a tidy header on the front of every message. We tried that. The connection opened, and - nothing. Dead air. Read attempts timed out no matter how we addressed it.

The trick, which we found by probing the thing directly rather than trusting the label, is that the board doesn't speak Modbus-TCP at all. It speaks the old serial dialect, Modbus-RTU, with its checksum and all, straight down the Ethernet socket. It's a translator that just shovels the bytes through to the serial brain inside it unchanged. Send it the serial frame and it answers instantly. Send it the textbook networked frame and it ignores you politely forever.

I want to be honest about something here: I couldn't have told the agent that up front, because I didn't know it. Nobody knew it until the board was poked and watched. That's the part no amount of careful wording on my end could have supplied - it had to be discovered, by trying things and reading what came back. Validate your assumptions early. It's the same in software as it is on deck.

---

## 3. What we actually built

The result is one Python file with no outside parts to install - which matters when the thing has to run on whatever host is bolted into a vehicle and when I need to provide simple code for further implementation by the more competent. It does two jobs. One half talks to the board in its serial dialect: builds the frames, runs the checksum, sends the commands, reads the answers. The other half puts up a web page and a small control interface behind it. You get one tile per channel - on, off, toggle, a live switch, and a momentary pulse you can set to however many seconds - plus all-on and all-off across the board. It checks the board's state every couple of seconds and shows you a little dot that goes green when it's talking and red when it isn't.

That's it. Nothing fancy. But everything on that page does what it says, and I watched every bit of it throw real relays before I trusted it.

---

## 4. How the conversation actually went

The whole thing came together over eleven back-and-forths. I think it's worth laying them out, because the shape of them is the interesting part.

**Table 1. The eleven turns.**

| # | What I said | What it was | What it got me |
|---|---|---|---|
| 1 | Build a webpage to run the relay at this address | The opening ask | The first version, and the protocol hunt |
| 2 | Nothing's connected — you can throw the relays to test | Permission | Real verification instead of guessing |
| 3 | The web page doesn't actually operate the board | A bug report | A genuine fault, found and fixed |
| 4 | Add the pulse buttons | A feature I'd left out | Momentary control per channel |
| 5 | Make this its own project and get it ready to publish | Packaging | A real repository, readme, license |
| 6 | Do both (the cleanup and the safety default) | Packaging | Locked to localhost; tidied up |
| 7 | The channel names get set later, at install on the ASV | A deferral | Left as placeholders, on purpose |
| 8 | This should be separate from my Starlink work — split it out | A correction | Its own isolated project |
| 9 | Put a picture of the interface in the project | Documentation | A screenshot in the readme |
| 10 | Now do a reliability fix — without the board connected | A constraint | A sturdier design, tested against a fake board |
| 11 | Write this up | This | The document you're reading |

A couple of those are worth dwelling on, because they sort into two very different piles.

Turn 3 - “it doesn't work” - turned out to be a bug the agent had written into its own first draft. The buttons weren’t there, the header was and any click on any header component just did nothing. This was because of a quoting mistake buried in how the page was generated. No way I could have prevented that with better instructions; it was a flaw in the build, not a gap in my ask. What's worth noting is that my report didn't have to be clever. “Does not operate the relay board” was enough to send it back to find and fix the thing. I didn't need to know why. I only needed to know it was wrong, which is exactly the kind of judgment I do have.

Turn 10 is the one I'm fondest of, because it's the most like real fieldwork.

---

## 5. The part where I wedged the board

While we were grabbing that screenshot, the board failed to respond. Not a hardware glitch - it went fully dead, stopped answering even a ping, the works. What happened is that the program had been opening a brand-new connection for every single command and dropping it again, and with the status check, my test commands, and everything else all reaching for the board at once, it ran the little thing clean out of connection slots and locked it up solid. The fix on the bench is a power cycle. The fix in the code is to stop doing the dumb thing.

So, after this was pointed out to me, I told the agent: rebuild it so it holds one connection open and reuses it - and do it without the board, because the board's offline now and on a vehicle it'll drop out for real anyway. That's the constraint that made it interesting. It couldn't just try the new version on the hardware. The agent stood up a fake relay board in software - same dialect, same one-connection-at-a-time behavior — and proved the rewrite against that: one connection is held and reused. New startup reconnect requests when the link drops, and no scrambling when eight relay requests hammer it at once.

I'll point out what I like about that. The need for the fix didn't come from anybody's foresight. It came from breaking the thing under load, the way you always learn the real limits of a piece of gear. And the verification got done with no hardware at all, by building a model of the board and testing against that. Adapt, improvise, overcome - it works on software too. Gunny Highway would be proud.

---

## 6. A better way to ask

Looking back, a lot of my eleven turns weren't really new ideas. They were things I'd wanted all along and just hadn't said, because I didn't think of it until their absence was staring at me. The pulse buttons. Wanting a real, separate, published project instead of “a script.” Wanting it to survive a flaky connection - which is obvious the moment you remember it's going on an unmanned boat. All of that was in the back part of my fore-brain at turn one. I just didn't get it out.

Here's what I'd hand the next person in my shoes — somebody who knows their instrument and their goal but not the code. You don't need to learn programming. You need to learn how to say what you already know, up front, in a way the agent can use. I'd cover eight things before I started:

1. **The device and how you reach it** — what it is, its address, how it's wired. It points the agent in the right direction. To be clear, the device was attached, powered on and tested operable with its own software first. Hardware operability is pre-proven.

2. **Everything you need it to do** — in your own terms. On, off, toggle, pulse, all-at-once. This is the one I shorted, and it's the one you're best equipped to list completely, because it's just your hands-on routine written down.

3. **Where it's going to live and work** — a bench tool and an unmanned vehicle are different animals and saying which one tells the agent how tough it has to be.

4. **What it's allowed to do to test, and what it must not** — “nothing's hooked up, throw the relays” is what let it actually prove the thing instead of guessing.

5. **What you don't know yet** — the channel names I was setting at install. Say so, and it leaves them as placeholders instead of guessing wrong.

6. **What you want to end up with** — a single program you can run, its own published project, a readme. Say it first and you save yourself three trips.

7. **How you want it proven** — and what to do when the hardware isn't there. Test it live; otherwise test it against a model.

8. **Who you are** — what you know, and that you don't write code. It sets the terms.

Notice what's not on that list: how to frame the protocol, how to build the page, how to handle the connections. That's the agent's job, and the discovery work is the agent's job, and frankly you don't want to be specifying any of it. You bring the “what” and the “why”. It brings the “how”.

---

## 7. How long this would have taken me alone

I'll put a number on it; with the honesty it deserves.

The conversation version — all eleven turns, including the breakage and the rebuild and the publishing — took maybe an hour of my actual attention. The increments landed minutes apart; the calendar spread was me being busy elsewhere, not the work taking days.

Now the other side. I can't truly measure what it'd take a person to build this from scratch without an agent, because nobody did. I estimated it the way I'd estimate any job I'm bidding - have the agent break it into pieces and put an optimistic, likely, and pessimistic number on each, then add them up properly.

**Table 2. What an unaided build would run, for a real programmer (hours).**

| Piece of the job | Best | Likely | Worst | Expected |
|---|---|---|---|---|
| Figuring out the board's odd dialect | 1.0 | 3.0 | 10.0 | 3.8 |
| The Modbus talking-to-the-board code | 1.0 | 2.5 | 6.0 | 2.8 |
| The web server behind the page | 1.0 | 2.0 | 5.0 | 2.3 |
| The page itself | 2.0 | 4.0 | 9.0 | 4.5 |
| Chasing down the bugs | 1.0 | 3.0 | 8.0 | 3.5 |
| The reliability rebuild | 1.0 | 3.0 | 8.0 | 3.5 |
| Testing, including the fake board | 1.0 | 2.5 | 6.0 | 2.8 |
| Packaging and publishing it | 0.5 | 1.5 | 4.0 | 1.8 |
| All of it |  |  |  | about 25 |

That comes to around twenty-five hours, give or take - call it three working days - and that's for a competent programmer, which I'm not. The biggest and shakiest line is figuring out the dialect, since without the agent's quick poke-and-watch loop you'd burn real time discovering the same thing we found in section 2.

The human-agent conversation got me there in roughly an hour against a twenty-five-hour baseline. Twenty-odd times faster, sure. But that's the wrong comparison for me, and I won't pretend otherwise. For me the honest comparison isn't an hour against twenty-five hours. It's a working tool against no tool - because the real alternative was me, not a programmer, sitting down to learn sockets and Modbus and front-end work first, which on any honest accounting either takes a great deal longer or simply never gets finished.

---

## 8. What I make of it

A division of labor showed up here that I think is the whole point. I brought what I know - the device, the job it does, where it's going, what it must never do, what “done” looks like to me. The agent brought what it knows - how to make the bytes line up, how to build the page, how to keep a flaky connection from killing the board - and, just as important, the ability to find out the things that can only be learned by trying. The two times the project went sideways that no instruction of mine could have prevented - the board's hidden dialect and the bug it wrote itself - both sat squarely on the agent's side of that line. That feels right to me.

I'll keep my feet on the ground about it. This is one job, one board, one afternoon. I wouldn't stretch these numbers over a big system, where the hard parts are the coordinating and the keeping-it-running for years, and a conversation won't carry you. But for the small, sharp, one-purpose tools that fill a working life in this field - the kind a capable hand always needed and rarely had time to build - this way of working is the real thing. I have the tool to prove it, and it throws relays on command.

*The tool, and the fuller technical write-up this is drawn from, live at https://github.com/amcleodUNH/waveshare-relay-web. The reliability work was checked against a software stand-in for the board, with no hardware connected. This piece was written in my voice with an AI's hands; the voice, attitude and judgments are mine, most of the typing was not.*
