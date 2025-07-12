# 💘 Poornimax – A College-Exclusive Social Interaction Platform

**Poornimax** is a full-stack, real-time social interaction web app disguised as a college portal. Designed exclusively for students with `@poornima.org` email IDs, it enables secure OTP login, compatibility-based matching, real-time messaging, and engaging social features — all wrapped in a responsive and stealthy interface.

> 🚨 This is a passion project made for learning purposes and is not affiliated with Poornima Group of Colleges.

---

## 🎯 Features

- 🔐 **Secure OTP Login** using official college emails
- 📝 **Signup** with college name, department, gender, DOB, bio, and more
- 💘 **Heart Matching System**  
  - Send hearts to users  
  - If mutual, they become *mutual crushes*  
  - Chat unlocks, private posts become visible
- 🧠 **First-Time Compatibility Quiz**  
  - Calculates compatibility %  
  - Displayed when visiting other profiles
- 📊 **Dashboard Stats**  
  - Hearts sent/received  
  - Profile views  
  - Friend count
- 👀 **Filtered Feed Sections**  
  - Recently joined  
  - Same department  
  - Same year  
  - Same college
- 💬 **Real-Time Chat**  
  - Powered by Django Channels, Daphne & WebSockets  
  - Available only to mutual crushes (friends)
- 💌 **Anonymous & Named Confessions**  
  - All users can view them  
  - Optional identity reveal
- 📸 **Posts**  
  - Image + caption  
  - Like, comment, and delete functionality
- 🧑‍💼 **Profile Management**  
  - View others' profiles with compatibility info  
  - Edit your profile  
  - Delete your account  
  - Logout
- 🧭 **Bottom Navigation Bar**  
  - Explore  
  - Home  
  - Post  
  - Friends  
  - Inbox
- 📱 **Fully Responsive UI**

---

## 🛠 Tech Stack

- **Backend**: Django, Django Channels, SQLite3
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Real-Time Communication**: Daphne, WebSockets
- **Auth**: OTP-based email verification

---

## 📁 Project Structure

poornimax/
├── accounts/ # Signup/Login & OTP verification
├── feed/ # Hearts, compatibility, posts, profile logic
├── chat/ # Real-time messaging logic
├── static/ # CSS, JS, media
├── templates/ # All HTML templates
├── db.sqlite3 # Database
└── manage.py
