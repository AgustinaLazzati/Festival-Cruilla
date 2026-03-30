import pandas as pd
import random

# Load fake artist names 
artists_df = pd.read_csv("Datasets/Fake_artist.csv")
artists = artists_df.iloc[:, 0].dropna().astype(str).tolist()

# User answers options
moods = ["happy", "sad", "angry", "chill"]
mood_weights = [0.35, 0.25, 0.15, 0.25] #Have different probabilities percentage since based on what is more likely

instruments = ["piano", "guitar", "drums", "trumpet", "dj", "violin", "synth", "bass"]
eras = ["70s", "80s", "90s", "2000s", "2010s", "futuristic", "medieval", "classical"]

num_samples = 5000

data = []

for _ in range(num_samples):
    artist = random.choice(artists)

    row = {
        "Artist": artist,
        "Mood_emoji": random.choices(moods, weights=mood_weights, k=1)[0],
        "Instrument": random.choice(instruments),
        "Era": random.choice(eras)
    }

    data.append(row)

user_df = pd.DataFrame(data)

user_df["Artist"] = user_df["Artist"].str.strip().str.lower()
artists_df["Artist"] = artists_df["Artist"].str.strip().str.lower()
artist_subset = artists_df[["Artist", "Genre", "Energy", "Main_Instrument"]]

Real_Artists_df = pd.read_csv("Datasets/Artistas_Cruilla.csv")

# Create a mapping from Fake Artist to Real Artist using index
fake_to_real = dict(zip(artists_df["Artist"], Real_Artists_df["Artist"]))

# Map real artist to each user row
user_df["Real_Artist"] = user_df["Artist"].map(fake_to_real)

# Merge
merged_df = pd.merge(
    user_df,
    artist_subset,
    left_on="Artist",
    right_on="Artist",
    how="left"
)

# Save df
#merged_df.to_csv("Datasets/Users_Answers.csv", index=False)


users_info = pd.read_csv("Datasets/Users_Answers.csv")

prompt = (
    "Create a short instrumental track in the style of " + users_info["Real_Artist"][1] +
    " artist. The music should be " + users_info["Mood_emoji"][1] + " and have a " + str(users_info["Energy"][1]) + 
    " energy level. It belongs to the " + users_info["Genre"][1] + " genre with a " + users_info["Era"][1] +
    " influence. Use " + users_info["Main_Instrument"][1] + " as the core instrumentation and include " +
    users_info["Instrument"][1] + "."
)

print ("-------PROMPT EXAMPLE -------")
print(prompt)