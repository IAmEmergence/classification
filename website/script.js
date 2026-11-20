'use strict';

/* ===== SETTINGS YOU MAY EDIT ===== */
const API_URL = '/recommend-destination';
/* ================================= */

/* The password lives only in this variable. It is gone when the page reloads. */
let password = '';

let lastMainView = 'loginView';
let stepIndex = 0;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const MAIN_VIEWS = ['loginView', 'quizView', 'resultView'];

const form = $('#destinationForm');
const steps = $$('.step', form);
const formError = $('#formError');
const loginError = $('#loginError');
const menu = $('#settingsMenu');
const menuBtn = $('#settingsBtn');
const choiceSyncs = [];

/* ---------- Views ---------- */

function showView(id) {
    $$('.view').forEach((view) => {
        view.hidden = view.id !== id;
    });
    if (MAIN_VIEWS.includes(id)) {
        lastMainView = id;
    }
    closeMenu();
    window.scrollTo(0, 0);
}

/* ---------- Settings menu ---------- */

function closeMenu() {
    menu.hidden = true;
    menuBtn.setAttribute('aria-expanded', 'false');
}

menuBtn.addEventListener('click', () => {
    const willOpen = menu.hidden;
    menu.hidden = !willOpen;
    menuBtn.setAttribute('aria-expanded', String(willOpen));
});

document.addEventListener('click', (event) => {
    if (!event.target.closest('.settings')) {
        closeMenu();
    }
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeMenu();
    }
});

/* Any element with data-open="someViewId" opens that page.
   Any element with data-back returns to the last main screen. */
document.addEventListener('click', (event) => {
    const opener = event.target.closest('[data-open]');
    if (opener) {
        showView(opener.dataset.open);
    } else if (event.target.closest('[data-back]')) {
        showView(lastMainView);
    }
});

/* ---------- Login ---------- */

$('#loginForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = $('#password');

    if (/[^\x20-\x7E]/.test(input.value)) {
        loginError.textContent = 'Use only standard keyboard characters.';
        return;
    }

    password = input.value;
    input.value = '';
    loginError.textContent = '';
    showView('quizView');
});

/* ---------- Choice buttons (built from each <select>) ---------- */

function buildChoices(select) {
    const label = $(`label[for="${select.id}"]`, form);
    const wrap = document.createElement('div');
    const buttons = [];

    wrap.className = 'choices';
    wrap.setAttribute('role', select.multiple ? 'group' : 'radiogroup');
    label.id = `${select.id}Label`;
    wrap.setAttribute('aria-labelledby', label.id);

    [...select.options].forEach((option) => {
        const button = document.createElement('button');
        const text = document.createElement('span');

        button.type = 'button';
        button.className = 'choice';
        text.textContent = option.textContent;

        if (option.dataset.img) {
            const image = new Image();
            image.src = option.dataset.img;
            image.alt = '';
            image.loading = 'lazy';
            image.addEventListener('error', () => image.remove());
            button.append(image);
            wrap.classList.add('with-images');
        }

        button.append(text);
        button.addEventListener('click', () => {
            if (select.multiple) {
                option.selected = !option.selected;
            } else {
                select.selectedIndex = option.index;
            }
            sync();
        });

        buttons.push(button);
        wrap.append(button);
    });

    function sync() {
        buttons.forEach((button, index) => {
            button.setAttribute('aria-pressed', String(select.options[index].selected));
        });
    }

    select.classList.add('visually-hidden');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    select.after(wrap);
    choiceSyncs.push({ select, sync });
}

function clearChoices() {
    choiceSyncs.forEach(({ select, sync }) => {
        select.selectedIndex = -1;
        sync();
    });
}

/* ---------- Step-by-step questions ---------- */

function showStep(index, moveFocus = true) {
    const isLast = index === steps.length - 1;
    stepIndex = index;

    steps.forEach((step, i) => {
        step.hidden = i !== index;
    });

    $('#backBtn').hidden = index === 0;
    $('#nextBtn').hidden = isLast;
    $('#submitBtn').hidden = !isLast;
    $('#progressBar').style.width = `${((index + 1) / steps.length) * 100}%`;
    $('#stepCount').textContent = `Question ${index + 1} of ${steps.length}`;
    formError.textContent = '';

    if (moveFocus) {
        $('label', steps[index]).focus({ preventScroll: true });
    }
}

function validateStep(step) {
    const field = $('input, select', step);

    if (field.tagName === 'SELECT') {
        const hasAnswer = field.selectedOptions.length > 0;
        formError.textContent = hasAnswer
            ? ''
            : field.multiple ? 'Pick at least one option.' : 'Pick an option.';
        return hasAnswer;
    }

    formError.textContent = field.checkValidity() ? '' : field.validationMessage;
    return field.checkValidity();
}

function goNext() {
    if (validateStep(steps[stepIndex])) {
        showStep(stepIndex + 1);
    }
}

$('#nextBtn').addEventListener('click', goNext);
$('#backBtn').addEventListener('click', () => showStep(stepIndex - 1));

/* ---------- Sending the answers ---------- */

function selectedNumbers(name) {
    return [...form.elements[name].selectedOptions].map((option) => Number(option.value));
}

function buildPayload() {
    const { budget, urbanRural, quietExciting, folkLegend } = form.elements;

    return {
        budget: Number(budget.value),
        climate: selectedNumbers('preferredClimate'),
        months: selectedNumbers('preferredMonths'),
        urban_or_rural: ['urban', 'rural'][Number(urbanRural.value)],
        terrain: selectedNumbers('excitingPlaces'),
        quiet_or_exciting: ['quiet', 'exciting'][Number(quietExciting.value)],
        activities: selectedNumbers('excitingActivities'),
        folk_legends: folkLegend.value === '1',
    };
}

function setLoading(isLoading) {
    const button = $('#submitBtn');
    button.disabled = isLoading;
    button.textContent = isLoading ? 'Finding...' : 'Find your favorite destinations!';
}

function rejectPassword() {
    password = '';
    loginError.textContent = 'That password was not accepted. Try again.';
    showView('loginView');
}

async function submitAnswers() {
    setLoading(true);

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': password,
            },
            body: JSON.stringify(buildPayload()),
        });

        if (response.status === 401) {
            rejectPassword();
            return;
        }
        if (response.status === 422) {
            formError.textContent = 'Some answers look invalid. Please review them.';
            return;
        }
        if (response.status === 429) {
            const retryAfter = response.headers.get('Retry-After');
        
            formError.textContent = retryAfter
                ? `Too many requests. Try again in ${retryAfter} seconds.`
                : 'Too many requests. Please try again later.';
            return;
        }
        if (!response.ok) {
            formError.textContent = 'Something went wrong. Please try again.';
            return;
        }

        const data = await response.json();
        const resultList = $('#resultList');
        resultList.replaceChildren();
        
        data['recommended-destination'].forEach((destination) => {
            const item = document.createElement('li');
            item.textContent = destination;
            resultList.append(item);
        });

        showView('resultView');
    } catch (error) {
        formError.textContent = 'Cannot reach the server. Check your connection and try again.';
    } finally {
        setLoading(false);
    }
}

form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (stepIndex < steps.length - 1) {
        goNext();
    } else if (validateStep(steps[stepIndex])) {
        submitAnswers();
    }
});

$('#restartBtn').addEventListener('click', () => {
    form.reset();
    clearChoices();
    showStep(0, false);
    showView('quizView');
});

/* ---------- Start ---------- */

$$('select', form).forEach(buildChoices);
steps.forEach((step) => {
    $('label', step).tabIndex = -1;
});
clearChoices();
showStep(0, false);
showView('loginView');
