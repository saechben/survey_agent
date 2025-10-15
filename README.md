# Survey Agent

## Overview
This project delivers a survey web app packaged in a Docker container. Participants connect through their mobile browsers, enter a shared password, and respond anonymously to surveys.

## Survey Experience
- Question types include rating scales, single choice, multiple choice, and free text.
- No usernames are collected; a single shared password grants access to keep participation anonymous.
- The UI is optimized for mobile screens to support quick participation on phones.

## Data Handling
- Responses are persisted in a database (engine to be defined) for durability.
- Aggregated statistics are generated per question to show how all respondents answered.
- Metrics refresh on a periodic schedule rather than real-time streaming updates.

## Deployment Notes
- The application runs inside a Docker container, enabling consistent setup across environments.
