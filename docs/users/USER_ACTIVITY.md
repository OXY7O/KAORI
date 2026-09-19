# User Management Activity

User mutations are part of Activity Audit Log and use event types such as `user_created`, `user_updated`, `user_activated`, `user_deactivated`, `user_password_reset`, and `user_deleted`.

Authentication events will be consolidated into the same archive-first lifecycle. The dedicated Login Activity menu is removed now; historical `auth_login_events` remains temporarily until a migration can copy or project existing events without losing retention and checksum guarantees.
