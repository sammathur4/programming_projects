const { createClient } = require("@supabase/supabase-js");
require("dotenv").config();
const fs = require('fs');

const supabaseUrl = process.env.SUPABASE_URL; 
const supabaseKey = process.env.SUPABASE_KEY; 
const supabase = createClient(supabaseUrl, supabaseKey);


class SupabaseSessionStore {
    constructor({bucketName = 'newbies-bot' } = {}) {
        this.supabase = supabase;
        this.bucketName = bucketName;
    }

    async sessionExists(options) {
        const { data, error } = await this.supabase
            .storage
            .from(this.bucketName)
            .list('', {
                search: `${options.session}.zip`
            });

        if (error) {
            console.error('Error checking session existence in bucket:', error.message);
            return false;
        }

        return data.length > 0; 
    }

    async save(options) {
        const sessionData = fs.readFileSync(`${options.session}.zip`);

        const { error } = await this.supabase
            .storage
            .from(this.bucketName)
            .upload(`${options.session}.zip`, sessionData, {
                upsert: true, 
            });

        if (error) {
            console.error('Error saving session data to Supabase bucket:', error.message);
            throw error;
        }

        console.log('Session data saved successfully to bucket!');
    }

    async extract(options) {
        const { data, error } = await this.supabase
            .storage
            .from(this.bucketName)
            .download(`${options.session}.zip`);

        if (error) {
            console.error('Error downloading session data from Supabase bucket:', error.message);
            return null;
        }

        fs.writeFileSync(options.path, Buffer.from(await data.arrayBuffer()));
        console.log('Session data extracted successfully from bucket!');
    }

    async delete(options) {
        const { error } = await this.supabase
            .storage
            .from(this.bucketName)
            .remove([`${options.session}.zip`]);

        if (error) {
            console.error('Error deleting session data from Supabase bucket:', error.message);
            throw error;
        }

        console.log('Session data deleted successfully from bucket!');
    }
}



async function storeBirthday(userId, birthday) {
  const { data, error } = await supabase.from("birthdays").upsert(
    { user_id: userId, birthday: birthday }, 
    { onConflict: ["user_id"] } 
  );

  if (error) {
    console.error("Error storing birthday:", error);
  } else {
    console.log("Birthday stored successfully:", data);
  }
}

async function checkBirthdaysToday() {
  const currentDate = new Date();
  const currentDay = currentDate.getDate();
  const currentMonth = currentDate.getMonth() + 1;
  const currentYear = currentDate.getFullYear();

  const { data, error } = await supabase
  .from('birthdays')
  .select('user_id')
  .ilike('birthday', `%-${currentMonth.toString().padStart(2, '0')}-${currentDay.toString().padStart(2, '0')}`);


  if (error) {
    console.error("Error fetching birthdays:", error);
    return;
  }

  if (data.length) {
    console.log(data);
    return data.map((user) => user.user_id);
  } else {
    return [];
  }
}

async function listBirthdaysInMonth(month = 0 ) {
    console.log('received month'+ month);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);

    
    const currentYear = today.getFullYear();
    let startOfMonth, endOfMonth, tomorrowDay;

    if (month >= 1 && month <= 12) {
        
        startOfMonth = new Date(currentYear, month - 1, 1); 
        endOfMonth = new Date(currentYear, month, 0); 
        tomorrowDay = "01";
    } else {
       
        startOfMonth = new Date(currentYear, today.getMonth(), 1); 
        endOfMonth = new Date(currentYear, today.getMonth() + 1, 0); 
        tomorrowDay = String(tomorrow.getDate()).padStart(2, '0');
    }

    endOfMonth.setDate(endOfMonth.getDate());
    
    const endOfMonthDay = String(endOfMonth.getDate()).padStart(2, '0');
    const monthString = String(startOfMonth.getMonth() + 1).padStart(2, '0'); 

    const { data, error } = await supabase.rpc('get_birthdays_in_range', {
        start_date: tomorrowDay,
        end_date: endOfMonthDay,
        month: monthString
    });

    if (error) {
        console.error("Error fetching birthdays:", error);
        return;
    }

    if (data.length) {
        console.log(data);
        return data.map(record => ({
            user_id: record.user_id,
            birthday: record.birthday 
        })).sort((a, b) => {
            const dayA = new Date(a.birthday).getDate(); 
            const dayB = new Date(b.birthday).getDate(); 
            return dayA - dayB;
        });
    } else {
        return [];
    }
}


module.exports = { storeBirthday, checkBirthdaysToday,listBirthdaysInMonth,SupabaseSessionStore };
