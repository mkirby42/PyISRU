---
title: Reviving My 2012 MacBook Pro as a Personal Server
description: Meh-ing my way to saving $15/month
image: galaxy.jpg
---

I spent all my high school graduation money (and then some) on a late 2012 13” Retina MacBook Pro. That machine carried me through undergrad. It’s the one I learned to code on. Naturally, it holds a lot of sentimental value—and I could never bring myself to get rid of it.

But let’s be honest: it’s showing its age. It can’t run the latest macOS, and while I could install Linux, that feels like a kind of zombie bastardization. This machine deserves better.

---

## So… What Now?

I currently pay about \\$15/month for an EC2 instance to host my personal blog (aka “please-hire-me” billboard). Being a cheapskate, saving that $15 sounded appealing. So I thought—why not turn the MacBook into a server?

Sure, AWS probably makes better use of the grid than I can, and yes, keeping a decade-old MacBook plugged in 24/7 might not be the most energy-efficient move—but hey, it sounded fun. And that’s reason enough.

---

## The Resurrection Begins

First challenge: the MagSafe charger was frayed and definitely a fire hazard. But it worked. I booted up and checked the Python version—3.7. Oof. I use 3.12 at work, so I tried to install it via Homebrew. No dice. Tried 3.9. Still nope.

Fine. Time for Docker.

Except… the latest Docker Desktop doesn’t run on this macOS version. So I had to hunt down the newest compatible version. Once installed, the trackpad started acting weird, so I ditched the GUI and SSH’d in from my main machine. Old-school.

---

## Setting Up the Stack

I spun up two Docker containers—one for the site app, one for a Cloudflare tunnel so I could expose it to the web without fighting with my router.

To keep the MacBook awake with the lid closed, I used:

```bash
sudo caffeinate -dimsu
```

With that, everything was humming along.

I updated my DNS by removing the A record from Route 53 and pointed my domain’s nameservers to Cloudflare. That change takes about 24 hours to propagate—so as Sturgill Simpson says, “The name of the game is hurry up and wait.”

One hiccup: the containers couldn’t talk to each other at first. Easy fix:

```bash
docker network create flask-net
```

Then I attached both containers to that network and configured a public hostname for the Cloudflare tunnel. After that—smooth sailing.

---

## Wrapping Up

This was my first real experiment with replacing cloud infrastructure using old personal hardware. And honestly? I think I want to do more of this. There’s something satisfying about breathing new life into a machine that meant a lot to me—and saving a few bucks in the process.
