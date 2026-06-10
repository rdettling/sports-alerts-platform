# Sports Intelligence Platform Roadmap

## Vision

Today, Live Game Alerts helps users follow teams and games and receive notifications when important game events occur.

The long-term vision is to evolve the platform into a personalized sports dashboard that helps users answer:

> What should I care about today?

Instead of forcing users to bounce between ESPN, Reddit, X, injury reports, and news sites, the platform should give them one place to see the most relevant developments for the teams and leagues they care about.

The end state is not a generic chatbot layered onto sports data.

It is a personalized sports home screen that understands:

- what the user follows
- what is important
- what deserves attention now
- how broad that attention should be at the team level versus the league level

---

# Current State (V1)

### Features

- User accounts and authentication
- Follow teams
- Follow games
- Alert preferences
- Email notifications
- Background worker architecture
- Sports data ingestion
- Alert evaluation pipeline

### Architecture

- React frontend
- FastAPI backend
- PostgreSQL
- Background workers
- Dockerized deployment

---

# V2: Sports Updates Feed

## Goal

Expand from game-state alerts into a broader stream of sports updates tied to teams and leagues.

At this stage, the system does not need a large taxonomy of event types.

The simpler model is:

- ingest headlines or updates
- store the raw source content
- run cheap AI classification into structured fields
- associate them to teams and leagues
- dedupe them
- rank them later

### Examples

- Bears QB injury headline
- Notre Dame recruiting headline
- Warriors trade rumor
- Major NFL-wide injury update
- AP poll movement story

### Technical Work

- One or more source integrations for updates/headlines
- Raw update ingestion and storage
- Cheap LLM classification into a strict schema
- Team and league entity mapping
- Dedupe logic
- URL and source storage
- Published-time tracking
- Optional lightweight tagging for later ranking
- Reclassification support when prompts or schema change

### Important Principle

Updates do not need to be hard-classified into rigid buckets at the start.

It is probably better to begin with a simple update model and only add lightweight tags or categories later if they clearly improve ranking or UI clarity.

AI can be used here, but in a constrained way.

The model should classify a raw update into structured output such as:

- scope: team or league
- associated league
- associated teams if any
- lightweight tags
- rough importance
- rationale

The model should not directly decide final user visibility.

The app should still apply deterministic rules on top of the classification output.

### Why This Matters

This creates the raw content layer for the personalized dashboard.

It is also likely the hardest operational part of the roadmap, because source quality, normalization, and entity mapping are messy in practice.

---

# V3: Dashboard Relevance

## Goal

Not every update belongs on the dashboard, and not every update deserves the same placement.

The system should determine what deserves attention before deciding how to present it.

This is the core product brain.

### Example

A user follows:

- Chicago Bears
- Golden State Warriors

And also follows:

- NFL

Potential updates:

- Bears starting QB injured
- Warriors sign a fringe bench player
- Star NFL player on another team suffers season-ending injury
- Generic rumor article with weak sourcing

The platform should determine:

- what is worth showing
- what is worth emphasizing
- what matters because of a direct team follow
- what matters because it is important to the broader league

For example:

- a Bears injury update may rank very high for Bears followers
- a major NBA rule change may rank high for NBA followers even if no specific team is attached
- a weakly sourced rumor may be suppressed even if it mentions a followed team

### Technical Challenges

- Importance scoring
- Recency decay
- Deduplication
- Source weighting
- AI classification quality control
- Weak-rumor suppression
- Dashboard ranking

### Questions To Solve

- What makes an update important?
- What should qualify as league-wide important?
- How many items belong on the first screen?
- How should relevance quality be evaluated?

### Why This Matters

Without a strong relevance layer, the product is just a filtered news feed.

With a strong relevance layer, it becomes a personalized ESPN-style dashboard.

---

# V4: Follow Semantics And Personalization

## Goal

Different follow scopes should produce different dashboard behavior.

Following a team should not mean the same thing as following a league.

### Example

User A:
- Follows the Bears and Warriors

User B:
- Follows the entire NFL

User C:
- Follows Notre Dame Football and the broader college football landscape

The same raw update may deserve:

- very high priority for a direct team follower
- medium priority for a league follower
- no visibility for someone outside that scope

This stage should consume the structured output from V2 classification rather than raw article text directly.

### Potential Signals

- Teams followed
- Leagues followed
- Update engagement
- Email engagement
- Click behavior
- Alert interaction history

### Technical Challenges

- Team-level versus league-level weighting
- Preference modeling
- Personalized re-ranking
- Cold start handling
- Feedback loops

### Why This Matters

This is where the product starts to feel genuinely personalized rather than merely filtered.

---

# V5: Dashboard And Digest Presentation

## Goal

Turn ranked updates into a useful dashboard and digest experience.

This stage is about packaging information clearly, not deciding what matters.

### Example Output

Dashboard sections such as:

- Most important for your teams
- Major league-wide developments
- Recent updates you may have missed

Digest output such as:

Chicago Bears
- Caleb Williams remains on track to start Week 1
- New injury report released

Golden State Warriors
- Frontcourt trade rumors continue

NFL
- Major non-Bears injury reshapes playoff outlook

### Technical Work

- Dashboard feed layout
- Grouping and ordering rules
- Digest assembly
- Scheduled digest generation
- Email delivery

### Why This Matters

This is the first major user-facing expression of the relevance system.

It should make the app feel like a true sports dashboard even without AI.

---

# V6: AI Summaries And Explanations

## Goal

Use AI to summarize and explain the updates the platform has already chosen to show.

### Example

Good morning Ryan.

The biggest development for your teams today is that the Bears received a favorable injury update while the broader NFL absorbed a major quarterback injury that could affect the playoff race.

For the Warriors, there is still no major roster move, but trade speculation remains active.

### Technical Challenges

- Prompt design
- Context assembly
- Hallucination mitigation
- Cost optimization
- Output consistency
- Quality evaluation

### Important Principle

The AI should explain and summarize information.

The AI should not decide what information is important.

Importance and ranking should already be determined by the platform before the model is invoked.

### Why This Matters

AI becomes valuable here because it improves communication quality on top of a grounded dashboard and ranking system.

---

# V7: Interactive Sports Analyst

## Goal

Allow users to ask questions about teams, leagues, and recent developments using grounded platform context.

### Example Questions

- What are the most important NFL developments I should care about today?
- Why is this Bears story ranked so high?
- What changed for the Warriors this week?
- What league-wide stories matter even though they are not about my teams?

### Technical Challenges

- Retrieval
- Context selection
- Tool use
- Evaluation
- Conversation memory

### Important Principle

This should not become generic sports chat.

It should be grounded in the platform's own updates, ranking, and personalization systems.

---

# Why This Roadmap Is Interesting

This project evolves from a simple alerting application into a system involving:

- sports update ingestion
- entity mapping
- ranking
- recommendation systems
- personalization
- dashboard design
- AI generation
- retrieval
- evaluation

The goal is not to bolt AI onto a sports app.

The goal is to build a personalized sports dashboard that determines what matters, adapts that information to each user's follow scope, and communicates it clearly.
