from enum import Enum
from tokenize import Token
from dataclasses import dataclass
import urllib3
import json
import jwt 
import logging

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
        return '{}: {} - {}'.format(self.status_code, self.error_code, self.message)

class NileConfigError(Exception):
    pass

class TokenValidationError(Exception):
    pass

@dataclass
class NileUser:
    id: int
    email: str
    orgs: dict
    current_org_id: int



def getNileClient():
    if not _nile_client:
        raise NileConfigError("Nile client is not instantiated.")
    return _nile_client

class NileClient(object):
    # TODO: allow developer auth
    def __init__(self,url):
        self.base_url = url
        self.active_users = {}
        try:
            data, headers = self._send("GET", "/health/ok", return_headers=True)
            print("Successfully connected to Nile, at " + url)
            print("Current Nile version: " + headers.get('X-NILE-VERSION',"n/a"))
        except:
            print("Failed to connect to Nile at " + url +" or Nile is unhealthy")

    def _send(self, method, endpoint, payload=None, return_headers=False, token=None):
        if not self.base_url:
            raise NileConfigError("Nile's URL is missing")
        if endpoint[0] != "/":
            raise ValueError(f"{endpoint} is not a valid endpoint, it must start with '/'")

        url = self.base_url + endpoint
        req_headers={'Content-Type': 'application/json'}

        if token:
            req_headers['Authorization'] = 'Bearer ' + token

        if payload:
            encoded_data = json.dumps(payload).encode('utf-8')
            resp = _http.request(method,url,body=encoded_data, headers=req_headers)
        else:
            resp = _http.request(method,url,headers=req_headers)

        if resp.status == 204:
            return {
                "status_code": 204,
                "error_code": "success_without_content",
                "message": "request successful, no response data"
            }
        elif resp.status >= 200 and resp.status <= 299:
            data = json.loads(resp.data.decode('utf-8'))
            if return_headers:
                return data, resp.headers
            else:
                return data
        elif resp.status == 404:
            raise NileError(resp.status, resp.status, "resource not found")

        elif resp.status >=400 and resp.status <= 499:
            data = json.loads(resp.data.decode('utf-8'))
            raise NileError(data['status_code'], data['error_code'], data['message'])
        else:
            raise NileError(resp.status, resp.status, "internal server error")

#########################
# User Auth starts here (TODO: separate modules)
########################

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
        data = self._send(method="POST", endpoint="/auth/login", payload=payload)
        token = data['token']
        try:
            self.get_user(token) # this loads the user details from Nile and generates an active session for the token
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
    
    def get_user(self, token, use_cache = True) -> NileUser:
        if self.active_users.get(token) and use_cache:
            return self.active_users.get(token)
        else: 
            if token:
                try:
                    user = self._send("GET", "/me", token=token)
                except NileError as ne:
                    # Looks like Nile invalidated the current user session, so we can't get it
                    return None
                n_user = NileUser(id=user['id'], email=user['email'], orgs=None, current_org_id=None)
                self.active_users[token] = n_user
                # populate the orgs while we are here, so we'll know we have them if needed later:
                self.get_orgs(token)
                return n_user
            else:
                return None

    def logout(self, token):
        '''
            Remove the active session for the token
        '''
        self.active_users.pop(token, None)

#######################
# Orgs
#######################
    # TODO: is there a reasonable way not to keep passing tokens into the library?
    def get_orgs(self, token):
        user = self.get_user(token)
        if user:
            if user.orgs:
                return user.orgs
            else:
                orgs = self._send("GET", "/orgs", token=token)
                user.orgs = orgs
                user.current_org_id = orgs[0]['id']
                return orgs
        else:
            return []

    def get_current_org(self, token):
        user = self.active_users.get(token)
        if user:
            return user.current_org_id
        else:
            return None

    def set_current_org(self, token, org):
        user = self.active_users.get(token)
        user.current_org_id = org

#####################
# Invites
####################

    def get_invites(self, token, just_current_org=True, just_current_user=True):
        #TODO: Org filter in Nile is currently a bit buggy, so I'm filtering here
        curr_org = self.get_current_org(token)
        user = self.get_user(token).id
        invites = self._send("GET","/invites",token=token)
        maybe_filter_orgs = [inv for inv in invites if inv.get('org') == int(curr_org) or not just_current_org]
        maybe_filter_users = [inv for inv in maybe_filter_orgs if inv['inviter'] == user or not just_current_user]

        return maybe_filter_users

    def accept_invite(self, invite_code, token):
        try:
            self._send("POST",f"/invites/{invite_code}/accept", token=token)
        except NileError as ne:
            if ne.error_code == "user_already_in_org":
                pass
            else:
                raise ne


#########################
# Entity creation APIs starts here (TODO: separate modules)
# TODO: Remove the org/token after we allow a "developer" connection that creates entities for all orgs
########################
    def entity_exists(self, name, org_id, token):
        try:
            self._send("GET",f"/admin/entities/{name}?org_id={org_id}", token=token)
            return True
        except NileError as ne:
            if ne.status_code == 404:
                return False
            else:
                raise ne

    def create_entity(self, schema, org_id, token):
        # TODO: When we get proper error on duplicates, we won't need to check if entity already exist
        # TODO: Schema validation here pls
        parsed = json.loads(schema)
        self.entity_exists(parsed['name'], org_id, token) 
        self._send("POST", f"/admin/entities?org_id={org_id}", payload=parsed, token=token)

##############
# Instances
###############
    '''
        This returns all instances of entity that belong to the current org
    '''
    def get_instances(self, entity, token, with_envelope=True):
        org_id = self.get_current_org(token)
        if org_id is None:
            return []
        data = self._send("GET", f"/custom-data/{entity}?org_id={org_id}", token=token)
        if with_envelope:
            return data
        else:
            res = []
            for instance in data:
                flat = instance['properties']
                flat['id'] = instance['id']
                res.append(flat)
            return res

    def get_instance(self, entity, id, token, with_envelope=True):
        org_id = self.get_current_org(token)
        if org_id is None:
            return None
        data = self._send("GET", f"/custom-data/{entity}/{id}?org_id={org_id}", token=token)
        if with_envelope:
            return data
        else:
            flat = data['properties']
            flat['id'] = data['id']
            return flat

    def create_instance(self, entity, instance, token):
        org_id = self.get_current_org(token)
        if org_id:
            self._send("POST", f"/custom-data/{entity}?org_id={org_id}", payload=instance, token=token)

    def update_instance(self, entity, id, instance, token):
        org_id = self.get_current_org(token)
        if org_id:
            formatted = {"properties": instance}
            self._send("PUT", f"/custom-data/{entity}/{id}?org_id={org_id}", payload=formatted, token=token)

    def delete_instance(self, entity, id, token):
        org_id = self.get_current_org(token)
        if org_id:
            self._send("DELETE", f"/custom-data/{entity}/{id}?org_id={org_id}", token=token)