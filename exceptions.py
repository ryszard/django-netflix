from djson.exceptions import JSONException

class NetflixAccountRequired(JSONException):
    pass

class NetflixAccountBlocked(JSONException):
    pass
