const phone = document.getElementById('phone');
const viewCard = document.getElementById('view-card');
const viewForm = document.getElementById('view-form');

const stateEmpty = document.getElementById('state-empty');
const stateLoading = document.getElementById('state-loading');
const stateReady = document.getElementById('state-ready');
const renewBtn = document.getElementById('renew-btn');
const expiryText = document.getElementById('expiry-text');

const cardPhoto = document.getElementById('card-photo');
const cardName = document.getElementById('card-name');
const cardRa = document.getElementById('card-ra');
const cardInstitute = document.getElementById('card-institute');

const editBtn = document.getElementById('edit-btn');
const cancelEditBtn = document.getElementById('cancel-edit-btn');
const formTitle = document.getElementById('form-title');
const userForm = document.getElementById('user-form');
const formMsg = document.getElementById('form-msg');

const menuBtn = document.getElementById('menu-btn');
const menuDropdown = document.getElementById('menu-dropdown');

const inputUsername = document.getElementById('input-username');
const inputFullname = document.getElementById('input-fullname');
const inputRa = document.getElementById('input-ra');
const inputInstitute = document.getElementById('input-institute');
const inputPhoto = document.getElementById('input-photo');

// Username vem do path: "/" -> null (cadastro novo) ; "/joaosilva" -> "joaosilva"
function getUsernameFromPath() {
  const path = window.location.pathname.replace(/^\/+/, '').replace(/\/+$/, '');
  return path.length ? path : null;
}

let currentUsername = getUsernameFromPath();
let currentUserExists = false;

function setQrState(name) {
  [stateEmpty, stateLoading, stateReady].forEach(el => el.classList.remove('active'));
  phone.classList.remove('state-empty', 'state-loading', 'state-ready');

  if (name === 'empty') {
    stateEmpty.classList.add('active');
    phone.classList.add('state-empty');
  } else if (name === 'loading') {
    stateLoading.classList.add('active');
    phone.classList.add('state-loading');
  } else if (name === 'ready') {
    stateReady.classList.add('active');
    phone.classList.add('state-ready');
  }
}

function showCardView() {
  viewCard.style.display = 'flex';
  viewForm.style.display = 'none';
}

function showFormView() {
  viewCard.style.display = 'none';
  viewForm.style.display = 'flex';
}

async function loadUser(username) {
  const res = await fetch(`/api/users/${encodeURIComponent(username)}`);
  if (res.status === 404) return null;
  return res.json();
}

function renderCard(user) {
  cardName.textContent = user.full_name;
  cardRa.textContent = user.ra;
  cardInstitute.textContent = user.institute;
  cardPhoto.src = user.photo_url ? user.photo_url : 'avatar-placeholder.svg';

  if (user.qr_expiry) {
    setQrState('ready');
    expiryText.textContent = `Código QR expira em ${user.qr_expiry}`;
  } else {
    setQrState('empty');
    expiryText.textContent = 'Código QR expirou. Toque em renovar.';
  }
}

async function renewQr() {
  setQrState('loading');
  try {
    const res = await fetch(`/api/users/${encodeURIComponent(currentUsername)}/renew-qr`, {
      method: 'POST',
    });
    const data = await res.json();
    // Pequeno delay pra manter a sensação de "carregando", igual ao app original
    setTimeout(() => {
      setQrState('ready');
      expiryText.textContent = `Código QR expira em ${data.qr_expiry}`;
    }, 1200);
  } catch (err) {
    setQrState('empty');
    expiryText.textContent = 'Falha ao renovar. Tente novamente.';
  }
}

function fillFormForEdit(user) {
  inputUsername.value = user.username;
  inputUsername.disabled = true; // não deixa trocar o username numa edição
  inputFullname.value = user.full_name;
  inputRa.value = user.ra;
  inputInstitute.value = user.institute;
  formTitle.textContent = `Editando: ${user.username}`;
  cancelEditBtn.style.display = 'inline-block';
}

function resetFormForNewUser() {
  userForm.reset();
  inputUsername.disabled = false;
  formTitle.textContent = 'Novo usuário e-Card';
  cancelEditBtn.style.display = currentUserExists ? 'inline-block' : 'none';
}

userForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  formMsg.textContent = '';
  formMsg.className = 'form-msg';

  const usernameToSave = inputUsername.disabled ? currentUsername : inputUsername.value.trim();
  if (!usernameToSave) {
    formMsg.textContent = 'Informe um username.';
    formMsg.className = 'form-msg error';
    return;
  }

  const fd = new FormData();
  fd.append('full_name', inputFullname.value.trim());
  fd.append('ra', inputRa.value.trim());
  fd.append('institute', inputInstitute.value.trim());
  if (inputPhoto.files[0]) {
    fd.append('photo', inputPhoto.files[0]);
  }

  try {
    const res = await fetch(`/api/users/${encodeURIComponent(usernameToSave)}`, {
      method: 'POST',
      body: fd,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      formMsg.textContent = 'Erro ao salvar: ' + (err.error || res.status);
      formMsg.className = 'form-msg error';
      return;
    }
    const user = await res.json();
    formMsg.textContent = 'Salvo com sucesso!';
    formMsg.className = 'form-msg success';

    // Redireciona pra URL do cartão criado/editado
    window.location.href = `/${encodeURIComponent(user.username)}`;
  } catch (err) {
    formMsg.textContent = 'Erro de rede ao salvar.';
    formMsg.className = 'form-msg error';
  }
});

editBtn.addEventListener('click', async () => {
  menuDropdown.classList.remove('open');
  const user = await loadUser(currentUsername);
  if (user) {
    fillFormForEdit(user);
    showFormView();
  }
});

cancelEditBtn.addEventListener('click', () => {
  if (currentUserExists) {
    showCardView();
  }
});

renewBtn.addEventListener('click', renewQr);

menuBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  menuDropdown.classList.toggle('open');
});

document.addEventListener('click', (e) => {
  if (!menuDropdown.contains(e.target) && e.target !== menuBtn) {
    menuDropdown.classList.remove('open');
  }
});

// ---------- Inicialização / roteamento ----------

async function init() {
  if (currentUsername) {
    const user = await loadUser(currentUsername);
    if (user) {
      currentUserExists = true;
      renderCard(user);
      showCardView();
      return;
    }
    // username na URL mas não existe ainda: já mostra o form pré-preenchido com o username
    currentUserExists = false;
    resetFormForNewUser();
    inputUsername.value = currentUsername;
    showFormView();
    return;
  }

  // Sem username na URL: tela de cadastro de novo usuário
  currentUserExists = false;
  resetFormForNewUser();
  showFormView();
}

init();