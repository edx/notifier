def enable_theme(theme_name):
    """
    Enable the settings for a custom theme, whose files should be stored
    in ENV_ROOT/themes/THEME_NAME (e.g., edx_all/themes/stanford).

    The THEME_NAME setting should be configured separately since it can't
    be set here (this function closes too early). An idiom for doing this
    is:
        THEME_NAME = os.getenv('THEME_NAME', None)
        enable_theme(THEME_NAME)
    """
    # Calculate the location of the theme's files
    theme_root = ENV_ROOT + "/themes/" + theme_name

    # Include the theme's templates in the template search paths
    try:
        TEMPLATE_DIRS
    except NameError:
        TEMPLATE_DIRS = [
                os.path.join(PROJECT_ROOT, "templates/"),
                ]
    TEMPLATE_DIRS.insert(0, theme_root + "templates/")

    # Namespace the theme's static files to 'themes/<theme_name>' to
    # avoid collisions with default edX static files
    try:
        STATICFILES_DIRS
    except NameError:
        STATICFILES_DIRS = [
                os.path.join(PROJECT_ROOT, "static/"),
                ]
    STATICFILES_DIRS.insert(0, ("themes/%s" % theme_name, theme_root + "/static"))


