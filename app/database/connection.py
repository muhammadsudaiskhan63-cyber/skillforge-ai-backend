import mysql.connector

connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="SkillForge123!",
    database="skillforge_ai"
)

cursor = connection.cursor()

print("Database Connected Successfully!")