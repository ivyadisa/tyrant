from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions
from rest_framework.authtoken.models import Token


class FlexibleTokenAuthentication(TokenAuthentication):
    """
    Token authentication that accepts both:
    - 'Token <token>' (standard DRF format)
    - '<token>' (Swagger/直接发送token的情况)
    """
    model = Token
    
    def authenticate(self, request):
        auth = request.headers.get('Authorization')
        
        if not auth:
            return None
        
        # Try standard format first: "Token <token>"
        if auth.startswith('Token '):
            return super().authenticate(request)
        
        # If just the token (no prefix), use it directly
        if auth:
            key = auth
            try:
                token = self.model.objects.get(key=key)
                return (token.user, token)
            except self.model.DoesNotExist:
                raise exceptions.AuthenticationFailed('Invalid token.')
        
        return None
