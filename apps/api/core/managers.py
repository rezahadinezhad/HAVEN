from django.contrib.auth.models import UserManager


class LocalUserManager(UserManager):
    def _create_user(self, username, email, password, **extra_fields):
        from django.contrib.auth.hashers import make_password

        if not username:
            raise ValueError("Username required")
        user = self.model(username=self.model.normalize_username(username), **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user
