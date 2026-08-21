import os
import streamlit as st
from dotenv import load_dotenv
from groq import Groq


# --------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="AI Workout Planner",
    page_icon="images/fitness_plan.png",
    layout="wide"
)


# --------------------------------------------------
# CSS
# --------------------------------------------------

st.markdown("""
<style>

/* Main page width */
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Main title */
h1 {
    margin-bottom: 0px;
}

/* Style bordered Streamlit containers as cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: white;
    border-radius: 18px;
    border: 1px solid #e6eaf0;
    padding: 10px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
}

/* Generate button */
.stButton > button {
    width: 100%;
    border-radius: 10px;
    height: 55px;
    font-size: 18px;
    font-weight: 600;
}

/* Text area */
.stTextArea textarea {
    border-radius: 10px;
}

/* Select boxes */
[data-baseweb="select"] > div {
    border-radius: 10px;
}

/* Number input */
[data-testid="stNumberInput"] input {
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# FUNCTION TO GENERATE WORKOUT PLAN
# --------------------------------------------------

def generate_workout_plan(
    goal: str,
    experience: str,
    days_per_week: int,
    equipment: list[str],
    limitations: str
) -> str:
    """
    Builds a workout prompt, calls the Groq API,
    and returns the generated workout plan.
    """

    try:

        # Convert equipment list into readable text
        equipment_text = ", ".join(equipment)

        # Build prompt from structured inputs
        prompt = f"""
        Create a personalized workout plan based on the following information:

        Fitness Goal: {goal}
        Experience Level: {experience}
        Days Available Per Week: {days_per_week}
        Equipment Available: {equipment_text}
        Injuries or Limitations: {limitations if limitations else "None"}

        Please create a practical and safe workout plan that matches
        the user's fitness goal, experience level, available equipment,
        and physical limitations.Please respect the constraints and injuries

        Please respect the user's constraints and injuries.

        For each workout day include:
        - Workout focus
        - Warm-up
        - Exercise name
        - Sets
        - Reps or duration
        - Rest time
        - Cool-down

        Also include:
        - A short weekly overview
        - Recovery advice
        - Safety advice

        Keep the workout plan clear, realistic, and easy to follow.
        """

        # Call Groq API
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful fitness coach who creates "
                        "safe and easy-to-follow workout plans."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Check if response is missing or malformed
        if (
            not response.choices
            or not response.choices[0].message
            or not response.choices[0].message.content
        ):
            return (
                "Sorry, I couldn't generate a workout plan. "
                "Please try again."
            )

        workout_plan = response.choices[0].message.content

        # Check if response content is empty
        if not workout_plan.strip():
            return (
                "Sorry, the workout plan came back empty. "
                "Please try again."
            )

        return workout_plan

    except Exception:
        return (
            "Sorry, something went wrong while generating your workout plan. "
            "Please check your internet connection or API key and try again."
        )


# --------------------------------------------------
# HEADER
# --------------------------------------------------

header_icon, header_title = st.columns([1, 10])

with header_icon:
    st.image("images/fitness_plan.png", width=60)

with header_title:
    st.title("AI Workout Planner")
    st.caption("Build a personalized workout plan powered by AI")

st.divider()


# --------------------------------------------------
# TWO-COLUMN LAYOUT
# --------------------------------------------------

left_column, right_column = st.columns(
    [1, 1.5],
    gap="large"
)


# --------------------------------------------------
# LEFT SIDE - USER INPUT CARD
# --------------------------------------------------

with left_column:

    with st.container(border=True):

        st.subheader("Create Your Plan")

        goal = st.selectbox(
            "🎯 Fitness Goal",
            [
                "Build muscle",
                "Lose fat",
                "General fitness",
                "Improve endurance"
            ]
        )

        experience = st.selectbox(
            "💪 Experience Level",
            [
                "Beginner",
                "Intermediate",
                "Advanced"
            ]
        )

        days_per_week = st.number_input(
            "📅 Days available per week",
            min_value=0,
            max_value=7,
            value=3,
            step=1
        )

        equipment = st.multiselect(
            "🏠 Equipment Available",
            [
                "No equipment",
                "Dumbbells",
                "Resistance bands",
                "Full gym"
            ]
        )

        limitations = st.text_area(
            "🩹 Injuries or limitations (Optional)",
            placeholder="e.g. Bad knees, no overhead pressing..."
        )

        generate_button = st.button(
            "✨ Generate Plan",
            use_container_width=True
        )


# --------------------------------------------------
# RIGHT SIDE - RESULT CARD
# --------------------------------------------------

with right_column:

    with st.container(border=True):

        st.subheader("🏋️ Your Personalized Workout Plan")

        if generate_button:

            # --------------------------------------
            # INPUT VALIDATION
            # --------------------------------------

            if days_per_week < 1:

                st.warning(
                    "Please select at least 1 workout day per week."
                )

            elif not equipment:

                st.warning(
                    "Please select at least one equipment option."
                )

            else:

                with st.spinner(
                    "Creating your personalized workout plan..."
                ):

                    workout_plan = generate_workout_plan(
                        goal=goal,
                        experience=experience,
                        days_per_week=days_per_week,
                        equipment=equipment,
                        limitations=limitations
                    )

                st.markdown(workout_plan)

                st.download_button(
                    label="Download Workout Plan",
                    data=workout_plan,
                    file_name="personalized_workout_plan.txt",
                    mime="text/plain",
                    use_container_width=True
                    )

        else:

            st.info(
                "Complete the form and click Generate Plan "
                "to create your personalized workout."
            )