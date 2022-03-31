from tokenize import Token
import urllib3
import json
import jwt 

# This is a fairly generic Python wrapper of Nile's REST APIs.
# We hope to publish a more complete version of this as a package eventually

_http = urllib3.PoolManager()
_nile_client = None

class NileError(Exception):
    def __init__(self, status_code, error_code, message):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return '{}: {}'.format(self.status_code, self.message)

class NileConfigError(Exception):
    pass

class TokenValidationError(Exception):
    pass

def getNileClient():
    if not _nile_client:
        raise NileConfigError("Nile client is not instantiated.")
    return _nile_client

class NileClient(object):
    def __init__(self,url):
        self.base_url = url
        self.active_users = {}

    def _send(self, method, endpoint, payload):
        if not self.base_url:
            raise NileConfigError("Nile's URL is missing")
        if endpoint[0] != "/":
            raise ValueError(f"{endpoint} is not a valid endpoint, it must start with '/'")

        url = self.base_url + endpoint

        encoded_data = json.dumps(payload).encode('utf-8')
        resp = _http.request(method,url,body=encoded_data, headers={'Content-Type': 'application/json'})
        if resp.status >= 200 and resp.status <= 299:
            data = json.loads(resp.data.decode('utf-8'))
            return data
        else:
            data = json.loads(resp.data.decode('utf-8'))
            raise NileError(data['status_code'], data['error_code'], data['message'])


    def signup(self, email, password,**kwargs):
        '''
            Create a new user 

            Args:
                email (string): Required. Email address serves as a unique identifier for users in Nile's User entity schema. Currently Nile validates uniqueness, but not whether the string is a valid email address.
                password (string): Required. Currently Nile does not enforce any password policy.

            Returns:
                is_successful (boolean): True if signup was successful

            Raises:
                NileError: Nile could not sign up the user
        ''' 
        payload = {
            'email' : email,
            'password' : password
        }
        self._send(method="POST",endpoint="/users",payload=payload)


    def login(self, email, password):
        '''
            Authenticate a user returning an authentication token that should be stored in a session cookie.
            This library will store a list of all tokens currently authenticated and Nile user data associated with them for quick reference (AKA, cache).

            Args:
                email (string): Required.
                password (string): Required.

            Returns:
                Authentication token. It is the caller responsibility to figure out how it will be handled with the client, since this library is independent of various webapp frameworks.
                In the Flask example, we store it in a session cookie. 
            
            Raises:
                NileError: Nile failed the login request
                TokenValidationError: Nile returned a token, but it was not a valid one. 
        '''
        payload = {
            'email' : email,
            'password' : password
        }
        data = self._send(method="POST", endpoint="/login", payload=payload)
        token = data['token']
        try:
            user = jwt.decode(token, options={"verify_signature": False})
            self.active_users[token] = user
            return token
        except jwt.exceptions.InvalidTokenError as ite:
            raise TokenValidationError(ite)

    #TODO: option to validate against Nile Server
    def validate_token(self, token):
        '''
            Check that the token is a valid one.
            Currently we just parse and check that it is stored on our cache. We'll introduce better validation when Nile does.

            Args:
                jwt token (string): Required.

            Returns:
                The token, if valid
            
            Raises:
                TokenValidationError: Token is invalid 
        '''
        try:
            jwt.decode(token, options={"verify_signature": False})
            self.active_users[token]
            return token
        except jwt.exceptions.InvalidTokenError as ite:
            raise TokenValidationError(ite)
        except:
            raise TokenValidationError("Token is parsable, but not a known active session")
    
    def getUserEmail(self, token):
        if self.active_users.get(token):
            return self.active_users.get(token).get('sub')
        else: 
            return None

    def logout(self, token):
        '''
            Remove the active session for the token
        '''
        self.active_users.pop(token, None)

    