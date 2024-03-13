// custom javascript

$( document ).ready(() => {
  console.log('Sanity Check Presto!');
  url = 'http://' + $(location).attr('hostname') + ':9181';
  console.log(url)

  const changeDateFormatTo = date => {
    const [yy, mm, dd] = date.split(/-/g);
    return `${dd}/${mm}/${yy}`;
  };

  $('#qr_dashboard').attr('src', url);

  $.ajax({
    url: '/all_tasks',
    method: 'GET'
  })
  .done((res) => {
    var html = `
        <tr>
          <td>Total: ${res.data.total}</td>
        </tr>`
        
    var tasks = res.data.tasks;
    $.each( tasks, function( key, value ) {
      // console.log( (parseInt(key)+1) + ": " + value );
      values = value.split('::')
      date = changeDateFormatTo(values[0])
      k = parseInt(key) + 1
      html += `<tr><td>${k}</td><td><a href="/tasks/${values[0]}${values[1]}" target="_blank">${date} ${values[1]}</a></td></tr>`
    });

    $('#alltasks').prepend(html);

    // setTimeout(function() {
    //   location.reload();
    // }, 50000);

  })
  .fail((err) => {
    console.log(err)
  });


  $('#date_wise_tasks').on('click', function(){
    date = $('#datepicker').val()
    // console.log(date);
    $.ajax({
      url: '/all_tasks/' + date,
      method: 'GET'
    })
    .done((res) => {
      var html = `
          <tr>
            <td>Total: ${res.data.total}</td>
          </tr>`
          
      var tasks = res.data.tasks;
      $.each( tasks, function( key, value ) {
        // console.log( (parseInt(key)+1) + ": " + value );
        values = value.split('::')
        date = changeDateFormatTo(values[0])
        k = parseInt(key) + 1
        html += `<tr><td>${k}</td><td><a href="/tasks/${values[0]}${values[1]}" target="_blank">${date} ${values[1]}</a></td></tr>`
      });
  
      $('#alltasksbydate').append(html);
  
    })
    .fail((err) => {
      console.log(err)
    });
  });


  $('#mac_wise_tasks').on('click', function(){
    mac = $('#mac').val()
    // console.log(date);
    $.ajax({
      url: '/all_tasks/mac/' + mac,
      method: 'GET'
    })
    .done((res) => {
      var html = `
          <tr>
            <td>Total: ${res.data.total}</td>
          </tr>`
          
      var tasks = res.data.tasks;
      $.each( tasks, function( key, value ) {
        // console.log( (parseInt(key)+1) + ": " + value );
        values = value.split('::')
        date = changeDateFormatTo(values[0])
        k = parseInt(key) + 1
        html += `<tr><td>${k}</td><td><a href="/tasks/${values[0]}${values[1]}" target="_blank">${date} ${values[1]}</a></td></tr>`
      });
  
      $('#alltasksbymac').append(html);
  
    })
    .fail((err) => {
      console.log(err)
    });
  });


  $('#restaurant_code_wise_tasks').on('click', function(){
    restaurant_code = $('#restaurant_code').val()
    // console.log(date);
    $.ajax({
      url: '/all_tasks/restaurant_code/' + restaurant_code,
      method: 'GET'
    })
    .done((res) => {
      var html = `
          <tr>
            <td>Total: ${res.data.total}</td>
          </tr>`
          
      var tasks = res.data.tasks;
      $.each( tasks, function( key, value ) {
        // console.log( (parseInt(key)+1) + ": " + value );
        values = value.split('::')
        date = changeDateFormatTo(values[0])
        k = parseInt(key) + 1
        html += `<tr><td>${k}</td><td><a href="/tasks/${values[0]}${values[1]}" target="_blank">${date} ${values[1]}</a></td></tr>`
      });
  
      $('#alltasksbyrestaurantcode').append(html);
  
    })
    .fail((err) => {
      console.log(err)
    });
  });


  $('.btn').on('click', function() {
    $.ajax({
      url: '/task',
      data: { type: $(this).data('type') },
      method: 'POST'
    })
    .done((res) => {
      getStatus(res.data.task_id)
    })
    .fail((err) => {
      console.log(err)
    });
  });
  
  function getStatus(taskID) {
    $.ajax({
      url: `/task_status/${taskID}`,
      method: 'GET'
    })
    .done((res) => {
      const html = `
        <tr>
          <td>${res.data.task_id}</td>
          <td>${res.data.task_status}</td>
          <td>${res.data.task_result}</td>
        </tr>`
      $('#tasks').prepend(html);
      const taskStatus = res.data.task_status;
      if (taskStatus === 'finished' || taskStatus === 'failed') return false;
      setTimeout(function() {
        getStatus(res.data.task_id);
      }, 1000);
    })
    .fail((err) => {
      console.log(err)
    });
  }
  
});






