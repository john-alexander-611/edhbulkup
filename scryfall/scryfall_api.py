import scrython

def get_face_commanders():
    face_commanders = set()
    commanders = scrython.cards.Search(q='otag:face-commander')
    for commander in commanders.data:
        face_commanders.add(commander.name)
    return face_commanders

def get_card_type(card_name: str):
    return str(scrython.cards.Named(fuzzy=card_name).type_line).lower()



if __name__ == "__main__":
    print(get_card_type("lightning bolt"))