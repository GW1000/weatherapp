# Commute Weather Alert Dispatcher

A serverless web application that allows users to schedule daily commute weather alerts. Users can register start and destination cities along with target schedule times, view active route subscriptions, or unsubscribe.

Features

* **Route Registration:** Accepts start and end cities, automatically geocodes location coordinates, and stores route details with custom departure times (default `07:00`).
* **Trip Management:** Allows users to query active trip subscriptions (`list`) or delete existing alerts (`unsubscribe`).
* **CORS Preflight Support:** Built-in handler for `OPTIONS` requests to support cross-origin browser fetch requests.
* **Serverless Backend:** Powered by AWS Lambda and DynamoDB for lightweight, scalable event processing.

File Overview

* `gmail_lambda_function.py`: AWS Lambda handler managing route actions, geocoding, and DynamoDB operations.
* `index.html`: Main frontend user interface for managing alert subscriptions.
* `.env.example`: Template for local environment variables and backend keys.
* `config.example.js`: Frontend configuration template for API endpoints.
* `register_users/`: Helper scripts or directory for user database workflows.

## API Specification

The Lambda endpoint processes JSON payloads containing an `action` key:

| Action | Required Fields | Description |
| :--- | :--- | :--- |
| `register` | `user_email`, `start_city`, `end_city` | Geocodes cities and creates a scheduled commute entry in DynamoDB. *(Optional: `schedule_time`)* |
| `list` | `user_email` | Returns all active trip subscriptions associated with the email address. |
| `unsubscribe` | `user_email` | Deletes the user record and route details from DynamoDB. |
