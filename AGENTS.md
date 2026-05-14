# AGENTS.md

## Product direction

This project is a Web desktop-first AI hiking forecast app, not a mobile app.

The desired UI style is:
- modern outdoor travel discovery website
- clean landing page
- large image cards
- rounded corners
- generous spacing
- soft shadows
- Swiss alpine visual identity
- clear feature navigation

Avoid:
- dense admin dashboard style
- mobile-only mockups
- unnecessary framework migration
- changing business logic when only UI is requested

## Frontend rules

Preserve existing app functionality:
- Find a hike
- Map
- Compare
- About
- model training / status
- trail catalogue and weather cache logic

When improving UI:
- Prefer small, focused changes
- Keep layout responsive
- Use desktop-first design
- Keep components reusable
- Do not remove working navigation
- Run available lint/test/format commands before finishing

## Streamlit-specific guidance

If this is a Streamlit app:
- Use layout="wide"
- Prefer st.columns and st.container for layout
- Use custom CSS for cards, hero, chips, and nav
- Avoid overusing st.metric on the landing page
- Keep custom CSS centralized