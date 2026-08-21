# AI Workout Planner

AI Workout Planner is a Streamlit application that generates a personalized workout plan based on a user's fitness goals, experience level, available days, equipment, and physical limitations.

The application uses the Groq API and the `openai/gpt-oss-20b` model to generate the workout plan.

## Features

* Select a fitness goal
* Select an experience level
* Choose training days per week
* Select available equipment
* Enter optional injuries or limitations
* Generate a personalized workout plan
* Input validation for missing or invalid inputs
* Error handling for API failures
* Friendly fallback message for empty or invalid LLM responses

## Technologies Used

* Python
* Streamlit
* Groq API
* `openai/gpt-oss-20b`
* python-dotenv

## Project Structure

```text
workout-planner/
│
├── app_final.py
├── README.md
├── .env
├── .gitignore
├── pyproject.toml
└── images/
    └── fitness_plan.png
```

## Setup

### 1. Install Dependencies

If using `uv`:

```bash
uv sync
```

Or install the packages manually:

```bash
pip install streamlit groq python-dotenv
```

### 2. Create Environment File

Create a `.env` file in the project folder:

```text
GROQ_API_KEY=your_groq_api_key_here
```

Do not commit your `.env` file to GitHub.

### 3. Run the Application

Using `uv`:

```bash
uv run streamlit run app.py
```

Or:

```bash
streamlit run app.py
```

## How It Works

1. The user enters their fitness preferences in the Streamlit interface.
2. The application validates the inputs.
3. The structured inputs are passed to a Python function.
4. The function builds a personalized prompt.
5. The prompt is sent to the Groq API.
6. The generated workout plan is returned.
7. Streamlit displays the workout plan to the user.

## Error Handling

The application handles:

* Missing or invalid user inputs
* Groq API failures
* Invalid API keys
* Network or rate-limit errors
* Empty or malformed LLM responses

Instead of crashing, the application displays a friendly error message.

## Security

The Groq API key is stored in a `.env` file and is not hardcoded in the Python source code.

The `.gitignore` file should contain:

```text
.env
.venv/
__pycache__/
```

## Disclaimer

The generated workout plans are for general informational purposes only. Users with injuries, medical conditions, or other health concerns should consult an appropriate qualified professional before starting a new exercise program.
