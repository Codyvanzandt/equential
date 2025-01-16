from app.config import get_settings
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from .database import init_db
from .models import User, Experiment, Choice, ClassificationItem, Option
from pathlib import Path
from fastapi.responses import RedirectResponse
import json
import random
from bayesian_testing.experiments import BinaryDataTest
import pandas as pd
import markdown2


app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/user/{access_id}")
async def get_user(access_id: str):
    user = await User.find_one({"access_id": access_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"Welcome {user.full_name}!"}

@app.post("/experiment/{experiment_id}/choice/{access_id}")
async def record_choice(
    experiment_id: str, 
    access_id: str, 
    choice: dict  # Simple dict with item_id and chosen_option
):
    user = await User.find_one({"access_id": access_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    success = await experiment.record_choice(
        user_email=user.email,
        item_id=choice["item_id"],
        chosen_option=choice["chosen_option"]
    )
    if not success:
        raise HTTPException(status_code=400, detail="Invalid item_id or chosen_option")
    
    return {"message": "Choice recorded successfully"}

@app.get("/experiment/{experiment_id}")
async def get_experiment(experiment_id: str):
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment

@app.get("/experiment/{experiment_id}/item/{item_id}/results")
async def get_item_results(experiment_id: str, item_id: str):
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    results = experiment.get_item_results(item_id)
    if not results:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return results

@app.get("/experiment/{experiment_id}/unanswered/{access_id}")
async def get_unanswered_items(experiment_id: str, access_id: str):
    user = await User.find_one({"access_id": access_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    unanswered = experiment.get_unanswered_items(user.email)
    return {
        "experiment_name": experiment.name,
        "user_email": user.email,
        "unanswered_count": len(unanswered),
        "items": unanswered
    }

@app.get("/admin/{access_id}")
async def admin_dashboard(request: Request, access_id: str):
    user = await User.find_one({"access_id": access_id})
    if not user or not user.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    experiments = await Experiment.find_all().to_list()
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "experiments": experiments, "access_id": access_id}
    )

@app.post("/admin/{access_id}/experiments/create")
async def create_experiment_admin(
    access_id: str,
    experiment_json: UploadFile = File(...)
):
    user = await User.find_one({"access_id": access_id})
    if not user or not user.is_admin:
        raise HTTPException(status_code=404, detail="Not found")

    # Read and parse JSON
    try:
        json_str = await experiment_json.read()
        experiment_data = json.loads(json_str)
        
        # Validate required fields
        required_fields = ["name", "instructions", "items", "category_descriptions"]
        missing_fields = [field for field in required_fields if field not in experiment_data]
        if missing_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Create items from JSON
        items = [
            ClassificationItem(
                item_id=str(i+1),  # Auto-generate IDs if not provided
                content=item["content"],
                options=[
                    Option(
                        id=f"{i+1}_{j}",  # Generate unique IDs like "1_0", "1_1" for item 1's options
                        text=opt["text"],
                        category=opt["category"]
                    )
                    for j, opt in enumerate(item["options"])
                ]
            )
            for i, item in enumerate(experiment_data["items"])
        ]
        
        # Extract categories from descriptions
        categories = sorted(list(experiment_data["category_descriptions"].keys()))
        
        experiment = await Experiment.create_experiment(
            name=experiment_data["name"],
            instructions=experiment_data["instructions"],
            items=items,
            categories=categories,
            category_descriptions=experiment_data["category_descriptions"]
        )
        
        # Automatically generate links for all non-admin users
        non_admin_users = await User.find({"is_admin": False}).to_list()
        for user in non_admin_users:
            await user.generate_experiment_link(str(experiment.id))
        
        return RedirectResponse(
            url=f"/admin/{access_id}", 
            status_code=303
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field in data structure: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Pre-render markdown with extras enabled
def render_markdown(text):
    if not text:
        return ""
    return markdown2.markdown(text, extras=[
        'break-on-newline',  # Convert newlines to <br>
        'fenced-code-blocks',  # Support ```code blocks```
        'tables',  # Support markdown tables
        'code-friendly'  # Better code handling
    ])

@app.get("/admin/{access_id}/experiments/{experiment_id}/results")
async def admin_experiment_results(request: Request, access_id: str, experiment_id: str):
    # Verify admin access
    user = await User.find_one({"access_id": access_id})
    if not user or not user.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    # Get all non-admin users for progress calculation
    users = await User.find({"is_admin": False}).to_list()
    
    # Prepare data for Bayesian testing
    test = BinaryDataTest()
    
    # Initialize counters for total votes per category
    category_votes = {cat: 0 for cat in experiment.categories}
    total_votes = 0
    
    # Count votes for each category across all items
    for item in experiment.items:
        votes_per_category = item.get_votes_per_category()
        for category, votes in votes_per_category.items():
            category_votes[category] += votes
            total_votes += votes
    
    # Add aggregated data for each category
    for category in experiment.categories:
        test.add_variant_data_agg(
            category,
            totals=total_votes if total_votes > 0 else 1,  # Ensure we have at least 1 total
            positives=category_votes[category]
        )
    
    # Evaluate test and convert to DataFrame
    results = test.evaluate()
    results_df = pd.DataFrame(results).set_index('variant').T
    
    # Create a single bayesian result for all data
    bayesian_results = [{
        'item_id': 'overall',
        'results': results_df
    }]
    
    # Pre-render markdown for items
    for item in experiment.items:
        item.content = render_markdown(item.content)
        for option in item.options:
            option.text = render_markdown(option.text)
    
    # Pre-render experiment instructions
    experiment.user_instructions = render_markdown(experiment.user_instructions)
    
    return templates.TemplateResponse(
        "admin/results.html",
        {
            "request": request,
            "experiment": experiment,
            "users": users,
            "access_id": access_id,
            "bayesian_results": bayesian_results
        }
    )

@app.get("/admin/{access_id}/experiments/{experiment_id}/export")
async def export_experiment_results(access_id: str, experiment_id: str):
    # Verify admin access
    user = await User.find_one({"access_id": access_id})
    if not user or not user.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    # Get all users who participated
    users = await User.find({"is_admin": False}).to_list()
    
    # Calculate overall stats per category
    total_votes = sum(len(item.choices) for item in experiment.items)
    votes_per_category = {cat: 0 for cat in experiment.categories}
    
    # Sum up votes per category across all items
    for item in experiment.items:
        item_votes = item.get_votes_per_category()
        for category, votes in item_votes.items():
            votes_per_category[category] += votes
    
    results = {
        "experiment": {
            "id": str(experiment.id),
            "name": experiment.name,
            "instructions": experiment.user_instructions,
            "categories": experiment.categories,
            "total_items": len(experiment.items),
            "total_users": len(users),
            "total_votes": total_votes,
            "total_possible_votes": len(experiment.items) * len(users),
            "votes_per_category": votes_per_category,
            "percentages_per_category": {
                cat: round((votes / total_votes * 100), 2) if total_votes > 0 else 0
                for cat, votes in votes_per_category.items()
            }
        }
    }

    return results

@app.get("/vote/{access_id}")
async def vote_interface(request: Request, access_id: str):
    user = await User.find_by_experiment_link(access_id)
    if not user:
        print(f"No user found for access_id: {access_id}")
        raise HTTPException(status_code=404, detail="Not found")
    
    experiment_id = await user.get_experiment_for_link(access_id)
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    # Get the next unanswered item
    unanswered = experiment.get_unanswered_items(user.email)
    if not unanswered:
        return templates.TemplateResponse(
            "vote/complete.html",
            {"request": request, "experiment": experiment}
        )
    
    # Randomly select an unanswered item
    current_item = random.choice(unanswered)
    
    # Shuffle the options before sending to template
    shuffled_item = current_item.copy()
    shuffled_item.options = random.sample(current_item.options, len(current_item.options))
    
    # Pre-render markdown
    rendered_instructions = render_markdown(experiment.user_instructions)
    rendered_content = render_markdown(shuffled_item.content)
    rendered_options = []
    for option in shuffled_item.options:
        rendered_options.append({
            "id": option.id,
            "text": render_markdown(option.text),
            "category": option.category
        })
    shuffled_item.options = rendered_options
    
    return templates.TemplateResponse(
        "vote/interface.html",
        {
            "request": request,
            "experiment": {
                **experiment.dict(),
                "user_instructions": rendered_instructions
            },
            "item": {
                **shuffled_item.dict(),
                "content": rendered_content,
                "options": rendered_options
            },
            "access_id": access_id,
            "remaining": len(unanswered)
        }
    )

@app.post("/vote/{access_id}")
async def submit_vote(
    access_id: str,
    item_id: str = Form(...),
    choice: str = Form(...)
):
    user = await User.find_by_experiment_link(access_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    
    experiment_id = await user.get_experiment_for_link(access_id)
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    await experiment.record_choice(user.email, item_id, choice)
    
    # Redirect back to the voting interface
    return RedirectResponse(
        url=f"/vote/{access_id}",
        status_code=303
    )

@app.get("/admin/{access_id}/users")
async def admin_users(request: Request, access_id: str):
    user = await User.find_one({"access_id": access_id})
    if not user or not user.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    users = await User.find({"is_admin": False}).to_list()
    
    # Get experiment links for each user
    for user in users:
        user.experiment_links = await user.get_experiment_links()
        # The links already contain experiment names, no need to fetch experiments again
    
    return templates.TemplateResponse(
        "admin/users.html",
        {"request": request, "users": users, "access_id": access_id}
    )

@app.post("/admin/{access_id}/users/create")
async def admin_create_user(
    access_id: str,
    email: str = Form(...),
    full_name: str = Form(...)
):
    admin = await User.find_one({"access_id": access_id})
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Create the new user
    user = await User.create_user(email=email, full_name=full_name)
    
    # Generate links for all existing experiments
    experiments = await Experiment.find_all().to_list()
    for experiment in experiments:
        await user.generate_experiment_link(str(experiment.id))
    
    return RedirectResponse(
        url=f"/admin/{access_id}/users",
        status_code=303
    )

@app.post("/admin/{access_id}/users/{user_id}/delete")
async def admin_delete_user(access_id: str, user_id: str):
    admin = await User.find_one({"access_id": access_id})
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await user.delete()
    
    return RedirectResponse(
        url=f"/admin/{access_id}/users",
        status_code=303
    ) 

@app.post("/admin/{access_id}/experiments/{experiment_id}/delete")
async def admin_delete_experiment(access_id: str, experiment_id: str):
    # Verify admin access
    user = await User.find_one({"access_id": access_id})
    if not user or not user.is_admin:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Get and verify experiment exists
    experiment = await Experiment.get(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    # Delete the experiment
    await experiment.delete()
    
    # Redirect back to dashboard
    return RedirectResponse(
        url=f"/admin/{access_id}",
        status_code=303
    ) 