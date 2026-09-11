document.addEventListener('DOMContentLoaded', () => {
    // 1. Scroll Spy para menú lateral
    const sections = document.querySelectorAll('.report-section');
    const navLinks = document.querySelectorAll('.nav-item a');

    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (pageYOffset >= sectionTop - 150) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.parentElement.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.parentElement.classList.add('active');
            }
        });
    });

    // 2. Funcionalidad de Copiar Código
    const codeHeaders = document.querySelectorAll('.code-header');
    codeHeaders.forEach(header => {
        const copyBtn = document.createElement('button');
        copyBtn.textContent = 'Copiar';
        copyBtn.style.background = 'transparent';
        copyBtn.style.border = '1px solid #475569';
        copyBtn.style.color = '#94a3b8';
        copyBtn.style.fontSize = '0.75rem';
        copyBtn.style.padding = '0.2rem 0.5rem';
        copyBtn.style.borderRadius = '4px';
        copyBtn.style.cursor = 'pointer';

        copyBtn.addEventListener('click', () => {
            const pre = header.nextElementSibling;
            if (pre && pre.tagName === 'PRE') {
                navigator.clipboard.writeText(pre.innerText).then(() => {
                    copyBtn.textContent = '¡Copiado!';
                    copyBtn.style.borderColor = '#38bdf8';
                    copyBtn.style.color = '#38bdf8';
                    setTimeout(() => {
                        copyBtn.textContent = 'Copiar';
                        copyBtn.style.borderColor = '#475569';
                        copyBtn.style.color = '#94a3b8';
                    }, 2000);
                });
            }
        });

        header.appendChild(copyBtn);
    });
});
