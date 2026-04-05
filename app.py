from flask import Flask, render_template, request
import re
import os
import json
from openai import OpenAI
client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key="api_key"
)

app = Flask(__name__)

def safe_json_load(raw):
    try:
        return json.loads(raw)
    except:
        print("RAW AI OUTPUT:", raw)
        raise

def ai_parse_tasks(tasks):

    prompt = f"""
Convert the following tasks into clean JSON.

IMPORTANT:
- Convert words like "five minutes" → 5 minutes
- Remove filler words like "look at", "do", "start", "maybe"
- Keep task names SHORT and clean

Example:
"look at art five minutes" → "Art Study"
"solve math problems ten mins" → "Math Practice"

Tasks:
{tasks}

Return ONLY JSON:
[
 {{"task":"clean task name","time_minutes":number}}
]
"""
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3-0324",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw)

    return safe_json_load(raw)

def ai_generate_plan(tasks, mood):


    prompt= f"""
You are an AI productivity planner.

User mood: {mood}

Tasks:
{tasks}

Instructions:
- Understand task durations (including words like "five minutes")
- Prioritize tasks based on mood:
    - stressed → small & easy tasks first
    - normal → balanced tasks
    - energetic → hardest tasks first
- Split very large tasks if user is stressed
- Decide which tasks to DO and which to POSTPONE
Advice Rules:
- Give 3 VERY PRACTICAL tips (not generic)
- Each tip should be actionable (what exactly to do)
- Adapt tips to mood AND tasks

Message Rules:
- Short (1 line)
- Emotionally supportive
- Personalized based on workload

Return ONLY JSON like:
{{
 "tasks":[
 {{
   "name":"task",
   "time":minutes,
   "status":"done/postpone",
   "reason":"why this decision was made"
 }}
],
 "advice":[
    "specific actionable tip 1",
    "specific actionable tip 2",
    "specific actionable tip 3"
 ],
 "message":"short motivational message"
}}
"""
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3-0324",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw)

    return safe_json_load(raw)

# 🧠 Flexible time parser
def parse_time(task):
    task = task.lower()
    # match days
    day_match = re.search(r'(\d+)\s*(d|day|days)', task)
    # match hours (h, hr, hrs, hour, hours)
    hour_match = re.search(r'(\d+)\s*(h|hr|hrs|hour|hours)', task)
    # match minutes (m, min, mins, minute, minutes)
    min_match = re.search(r'(\d+)\s*(m|min|mins|minute|minutes)', task)

    total_minutes = 0

    if day_match:
        total_minutes += int(day_match.group(1)) * 60 * 24

    if hour_match:
        total_minutes += int(hour_match.group(1)) * 60

    if min_match:
        total_minutes += int(min_match.group(1))

    # default if no time mentioned
    if total_minutes == 0:
        total_minutes = 60

    return total_minutes

def extract_task(task):
    original = task.strip()
    task_lower = original.lower()

    # 🧠 get time using existing function
    minutes = parse_time(task_lower)

    # 🧹 remove time part from task
    cleaned = re.sub(
        r'\d+\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes)',
        '',
        task_lower
    )

    # remove symbols like - or –
    cleaned = re.sub(r'[-–]', '', cleaned)

    # clean spaces
    cleaned = cleaned.strip()

    # capitalize nicely
    cleaned = cleaned.title()

    return {
        "original": original,
        "name": cleaned,
        "minutes": minutes
    }

def format_time(minutes):
    if minutes >= 60:
        return f"{minutes//60}h {minutes%60}m" if minutes % 60 else f"{minutes//60}h"
    return f"{minutes}m"

# 🚀 Smart planner logic
def generate_plan(tasks, mood):
    try:
        ai_result = ai_generate_plan(tasks, mood)

        tasks_output = [
            {
                "name": t["name"].title(),
                "time": format_time(int(t["time"])),
                "minutes": int(t["time"]),
                "status": t["status"],
                "reason": t.get("reason", "")
            }
            for t in ai_result["tasks"]
        ]

        advice = ai_result["advice"]
        message = ai_result["message"]

    except Exception as e:
        print("AI failed:", e)

        # 🔥 fallback smart logic
        task_list = [t.strip() for t in tasks.split("\n") if t.strip()]

        task_data = []
        for task in task_list:
            minutes = parse_time(task)
            task_data.append((task, minutes))

        # 🧠 mood-based sorting
        if mood == "stressed":
            task_data.sort(key=lambda x: x[1])  # small first
        elif mood == "energetic":
            task_data.sort(key=lambda x: -x[1]) # big first
        else:
            avg = sum(t[1] for t in task_data)/len(task_data) if task_data else 0
            task_data.sort(key=lambda x: abs(x[1]-avg))

        tasks_output = []
        used_time = 0
        limit = 480

        for task, minutes in task_data:
            if used_time + minutes <= limit:
                status = "done"
                used_time += minutes
            else:
                status = "postpone"

            tasks_output.append({
                "name": task.title(),
                "time": format_time(minutes),
                "minutes": minutes,
                "status": status
            })

        return {
            "status": "✨ Smart Plan Generated",
            "tasks": tasks_output,
            "advice": [
                "Start with smaller tasks to build momentum",
                "Take short breaks after each task",
                "Focus on one task at a time"
            ],
            "message": "Your personalized plan is ready 🚀",
            "chart": [
                {"name": t["name"], "time": t["minutes"]}
                for t in tasks_output if t["status"] == "done"
            ]
        }, used_time, 0

    # calculations
    total_time = sum(t["minutes"] for t in tasks_output)
    used_time = sum(t["minutes"] for t in tasks_output if t["status"] == "done")

    status = f"⚠️ {format_time(total_time)} planned" if total_time > 480 else f"✅ {format_time(total_time)} planned"

    return {
        "status": status,
        "tasks": tasks_output,
        "advice": advice,
        "message": message,
        "chart": [
            {
                "name": t["name"],
                "time": int(t["minutes"])
            }
            for t in tasks_output if t["status"] == "done"
        ]
    }, used_time, (total_time - used_time)


# 🌐 Flask route
@app.route("/", methods=["GET", "POST"])
def index():
    data = None
    planned_time = None
    postponed_time = None

    if request.method == "POST":
        tasks = request.form["tasks"]
        mood = request.form.get("mood", "normal")

        data, planned_time, postponed_time = generate_plan(tasks, mood)

    return render_template(
        "index.html",
        data=data,
        planned_time=planned_time,
        postponed_time=postponed_time
    )


if __name__ == "__main__":
    app.run(debug=True)
