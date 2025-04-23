from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

app = Flask(__name__)

# Load food data
food_data = pd.read_csv("food.csv")

def calculate_nutrients(age, weight, height, gender, activity_level, disorders):
    if isinstance(disorders, list):
        disorders = ",".join(disorders)
    
    if gender.lower() == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    
    activity_multipliers = {
        "sedentary": 1.2,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "super_active": 1.9
    }
    tdee = bmr * activity_multipliers.get(activity_level, 1.2)

    user_nutrients = {
        "Calories": tdee,
        "Carbohydrates": tdee * 0.45 / 4,
        "Proteins": tdee * 0.2 / 4,
        "Fats": tdee * 0.25 / 9,
        "Fibre": 25 if tdee < 2000 else 30,
        "Sodium": 2300,
        "Potassium": 3500,
        "Calcium": 1000,
        "Iron": 8 if gender.lower() == "male" else 18,
        "VitaminD": 15
    }

    if disorders.lower() != "none":
        disorder_list = [d.strip().lower() for d in disorders.split(",")]
        
        if "diabetes" in disorder_list:
            user_nutrients["Carbohydrates"] *= 0.8
            user_nutrients["Fibre"] += 5
        if "hypertension" in disorder_list:
            user_nutrients["Sodium"] = min(user_nutrients["Sodium"], 1500)
            user_nutrients["Potassium"] += 500
        if "pcos" in disorder_list:
            user_nutrients["Proteins"] += 10
            user_nutrients["Carbohydrates"] *= 0.85
            user_nutrients["Fibre"] += 5
        if "kidney disease" in disorder_list:
            user_nutrients["Sodium"] = min(user_nutrients["Sodium"], 1500)
            user_nutrients["Potassium"] = max(user_nutrients["Potassium"] - 1000, 2000)
            user_nutrients["Proteins"] *= 0.8
        if "hyperthyroidism" in disorder_list:
            user_nutrients["Calcium"] += 200
            user_nutrients["VitaminD"] += 5
            user_nutrients["Proteins"] += 10
    
    return pd.Series(user_nutrients)

# Function to recommend meals based on user nutrient requirements
def recommend_meals(nutrient_requirements, food_data, user_disorders, top_n=9):
    nutrient_columns = ["Calories", "Carbohydrates", "Proteins", "Fats", "Fibre", "Sodium", "Potassium", "Calcium", "Iron", "VitaminD"]
    
    for disorder in user_disorders:
        disorder = disorder.capitalize()
        if disorder in food_data.columns:
            food_data = food_data[food_data[disorder] == 1]
    
    X = food_data[nutrient_columns]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    user_input = np.array([nutrient_requirements[col] for col in nutrient_columns]).reshape(1, -1)
    user_input_scaled = scaler.transform(user_input)
    
    knn = NearestNeighbors(n_neighbors=min(top_n, len(food_data)), metric='euclidean')
    knn.fit(X_scaled)
    distances, indices = knn.kneighbors(user_input_scaled)
    
    meal_recommendations = []
    total_calories = 0
    for idx in indices[0]:
        food_item = food_data.iloc[idx]["Food_items"]
        food_nutrients = food_data.iloc[idx][nutrient_columns].to_dict()  # Nutritional info for the food item
        
        if total_calories + food_nutrients["Calories"] <= nutrient_requirements["Calories"]:
            total_calories += food_nutrients["Calories"]
            meal_times = []
            if food_data.iloc[idx]["Breakfast"] == 1:
                meal_times.append("Breakfast")
            if food_data.iloc[idx]["Lunch"] == 1:
                meal_times.append("Lunch")
            if food_data.iloc[idx]["Dinner"] == 1:
                meal_times.append("Dinner")
                
            meal_recommendations.append({
                "food_item": food_item,
                "nutrients": food_nutrients,
                "meal_times": meal_times
            })
    
    return meal_recommendations

# Function to generate a pie chart
def generate_pie_chart(recommendations):
    total_nutrients = {"Carbohydrates": 0, "Proteins": 0, "Fats": 0}
    for meal in recommendations:
        for key in total_nutrients:
            total_nutrients[key] += meal["nutrients"].get(key, 0)
    
    labels = total_nutrients.keys()
    sizes = total_nutrients.values()
    colors = ['#ff9999','#66b3ff','#99ff99']
    
    plt.figure(figsize=(5,5))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
    plt.axis('equal')  
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/recommend', methods=['POST'])
def recommend():
    age = int(request.form['age'])
    weight = float(request.form['weight'])
    height = float(request.form['height'])
    gender = request.form['gender']
    activity_level = request.form['activity_level']
    disorders = request.form.getlist('disorders')

    user_nutrients = calculate_nutrients(age, weight, height, gender, activity_level, disorders)
    meal_recommendations = recommend_meals(user_nutrients, food_data, disorders)
    pie_chart = generate_pie_chart(meal_recommendations)

    return render_template('recommendations.html', meals=meal_recommendations, pie_chart=pie_chart)

if __name__ == '__main__':
    app.run(debug=True)
