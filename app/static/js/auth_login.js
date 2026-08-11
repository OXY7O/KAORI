document.addEventListener('DOMContentLoaded', () => {
    const renderIcons = () => {
        if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    renderIcons()

    const passwordInput = document.querySelector('[data-password-input]')
    const passwordToggle = document.querySelector('[data-password-toggle]')
    const passwordIcon = document.querySelector('[data-password-icon]')

    if (passwordInput && passwordToggle) {
        passwordToggle.addEventListener('click', () => {
            const showingPassword = passwordInput.type === 'text'
            passwordInput.type = showingPassword ? 'password' : 'text'
            passwordToggle.setAttribute('aria-label', showingPassword ? 'Show password' : 'Hide password')

            if (passwordIcon) {
                passwordIcon.setAttribute('data-lucide', showingPassword ? 'eye' : 'eye-off')
                renderIcons()
            }
        })
    }

    const themeToggle = document.getElementById('auth-theme-toggle')
    const themeIcon = document.getElementById('auth-theme-icon')

    const updateThemeIcon = () => {
        if (!themeIcon) {
            return
        }

        const dark = document.documentElement.classList.contains('dark')
        themeIcon.setAttribute('data-lucide', dark ? 'sun' : 'moon')
        renderIcons()
    }

    updateThemeIcon()

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark')
            const dark = document.documentElement.classList.contains('dark')
            localStorage.setItem('theme', dark ? 'dark' : 'light')
            updateThemeIcon()
        })
    }
})
