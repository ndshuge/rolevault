TRUST={'owner_statement':1.0,'owner_confirmed':0.95,'verified_tool':0.8,'third_party':0.3,'rumor':0.1}

def score(source_type):
    return TRUST.get(source_type,0.0)

def can_override(old,new):
    return score(new.source_type) >= score(old.source_type)
